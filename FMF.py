# FriendMyFriend Server Side Tracker API
# Inteded to be used in a constantly running script
# Made by Clay Shieh
# Referenced Vladimir Smirnov's iCloud API Implementation code for general iCloud authentication workflow and cookie implementation
# https://github.com/mindcollapse/iCloud-API/

import os, httplib2, uuid, json, time
from Cookie import SimpleCookie

class FMFException(Exception):
	def __init__(self, value):
		self.value = value
	
	def __str__(self):
		return repr(self.value)

class FMF():
	def __init__(self, aid, password):
		#credentials
		self.aid = aid
		self.password = password
		self.build_id = "17DProject104"
		self.client_id = str(uuid.uuid1()).upper()
		self.dsid = None

		#connection
		self.cookies = SimpleCookie()
		self.http = httplib2.Http()

		#local
		self.fmf_base_url = None
		self.contacts = None
		self.fmf_map = None

		#cached info
		if os.path.isfile("./contacts.json"):
			self.contacts = self.persistant_read("./contacts.json")
		if os.path.isfile("./fmf.json"):
			self.fmf_map = self.persistant_read("./fmf.json")

	def persistant_write(self, fname, data):
		#data is a dictionary
		with open(fname, 'w') as f:
			json.dump(data, f)

	def persistant_read(self, fname):
		with open(fname, 'r') as f:
			return json.load(f)

	# referenced code
	def prepare_cookies(self):
		return self.cookies.output(sep=";", attrs=["value"], header="").strip()

	# referenced code
	def update_cookies(self, header):
		if "set-cookie" in header:
			hcookies = header["set-cookie"]
			tmp = SimpleCookie()
			tmp.load(hcookies)

			for cookie in tmp:
				self.cookies[cookie] = tmp[cookie].value

	def request(self, url, method="GET", headers=None, body=None, wait_time=10):
		rheader, data = None, None

		count = 0
		max_tries = 3
		exp_time = 0.0625

		#bad code practice. If LAN is down then it will hit the exception case
		#if apple server is down then itll get stuck in while loop and try with exponential backoff
		while rheader == None and data == None:
			try:
				rheader, data = self.http.request(url, "POST", 
							headers=headers,
							body=body
						)
			except Exception as e:
				print "Error in request"
				print e
				rheader, data = None, None
				time.sleep(wait_time)
				continue
			#just in case
			if count > max_tries:
				print "Max tries reached"
				if exp_time <= 16384: #lowest freq is ~ once per hr for apple server to come up
					exp_time *= 2
					count = 0
			count += 1
			time.sleep(exp_time)

		return rheader, data


	def get_service_url(self, resp, service):
		if resp:
			if service in resp["webservices"].keys():
				if resp["webservices"][service]["status"] == "active":
					self.fmf_base_url = resp["webservices"][service]["url"]
					return
		raise FMFException("Please check that FMF is enabled on your iCloud account.")

	def get_dsid(self, resp):
		if resp:
			self.dsid = resp["dsInfo"]["dsid"]
		else:
			raise FMFException("Please check that your login information is correct.")

	def authenticate(self):
		auth_url = "https://setup.icloud.com/setup/ws/1/login?clientBuildNumber={0}&clientId={1}"
		auth_url = auth_url.format(self.build_id, self.client_id)

		headers = {
			"Origin":"https://www.icloud.com", 
			"Referer":"https://www.icloud.com", 
			"Cookie":self.prepare_cookies()
		}

		data = {
			"apple_id":self.aid, 
			"password":self.password, 
			"extended_login":False
		}

		rheader, data = self.request(auth_url, "POST", 
						headers=headers,
						body=json.dumps(data)
					)

		self.update_cookies(rheader)

		auth_resp = json.loads(data)
		self.get_dsid(auth_resp)
		self.get_service_url(auth_resp, "fmf")

	def refresh(self, init=False):
		action = "refresh"
		if init:
			action = "init"

		fmf_url = "{0}/fmipservice/client/fmfWeb/{1}Client?clientBuildNumber={2}&clientId={3}&dsid={4}"

		headers = {
			"Origin":"https://www.icloud.com",
			"Referer":"https://www.icloud.com",
			"Cookie":self.prepare_cookies()
		}

		data = {
			"clientContext":{
				"productType":"fmfWeb",
				"appVersion":"1.0",
				"contextApp":"com.icloud.web.fmf",
				"userInactivityTimeInMS":1,
				"tileServer":"Apple"
			}
		}

		fmf_url = fmf_url.format(self.fmf_base_url, action, self.build_id, self.client_id, self.dsid)

		rheader, data = self.request(fmf_url, "POST", 
						headers=headers,
						body=json.dumps(data)
					)

		#update the cookies
		self.update_cookies(rheader)

		#process data
		data = json.loads(data)

		#get contacts
		name2id = {}
		tmp = []
		for contact in data["contactDetails"]:
			name = contact["firstName"] + " " + contact["lastName"]
			name2id[name] = contact["id"]
			tmp.append(contact["id"])
		ids = set(tmp)

		#get locations
		#k: id
		#v: [timestamp(ms), country, streetname, streetaddress, coutnrycode, locality, statecode, administrativearea]
		fmf_map = {}
		for location in data["locations"]:
			if location["location"]:
				timestamp = str(location["location"]["timestamp"])
				address = location["location"]["address"]
				if address:
					try:
						country = address["country"]
						countrycode = address["countryCode"]
						statecode = address["stateCode"]
						administrativearea = address["administrativeArea"]
						locality = address["locality"]
						streetname = address["streetName"]
						streetaddress = address["streetAddress"]

						fmf_map[location["id"]] = [timestamp, country, streetname, streetaddress, countrycode, locality, statecode, administrativearea]
					except KeyError:
						#add resolution tiers later
						pass
				continue #sometimes address isn't ready yet

		return ids, name2id, fmf_map

	def find(self, tries=5, wait_time=3):
		#run init first
		ids, contacts, fmf_map = self.refresh(init=True)

		for _ in range(tries):
			if set(fmf_map.keys()) == ids:
				break
			ids, contacts, new_fmf_map = self.refresh()
			for f in new_fmf_map:
				fmf_map[f] = new_fmf_map[f]
			time.sleep(wait_time)

		self.persistant_write("contacts.json", contacts)
		self.persistant_write("fmf.json", fmf_map)

		self.contacts = contacts
		self.fmf_map = fmf_map

	def get_user(self, user, hook=None):
		#use hooks as functions to run other utilities with that information
		if user in self.contacts:
			result = self.fmf_map[self.contacts[user]]
			print result
			if hook:
				hook(user, result)
			return result
		print "User not in contacts"
		return None
