# FriendMyFriend Server Side Tracker API
# Inteded to be used in a constantly running script
# Made by Clay Shieh
# Referenced Vladimir Smirnov's iCloud API Implementation code for general iCloud authentication workflow and cookie implementation
# https://github.com/mindcollapse/iCloud-API/

import os
import uuid
import json
import time
import requests
import logging


class FMFException(Exception):
	def __init__(self, value):
		self.value = value
	
	def __str__(self):
		return repr(self.value)


class FMF():
	def __init__(self, aid, password, cache=True, verbose=True):
		# credentials
		self.aid = aid
		self.password = password
		self.build_id = "17DProject104"
		self.client_id = str(uuid.uuid1()).upper()
		self.dsid = None

		# connection
		self.cookies = None
		self.http = requests.Session()

		# local
		self.fmf_base_url = None
		self.contacts = None
		self.fmf_map = None
		self.first_run = True

		# cached info
		self.cache = cache
		if self.cache:
			self.path = os.path.dirname(os.path.abspath(__file__))
			self.cpath = os.path.join(self.path, "contacts.json")
			self.fpath = os.path.join(self.path, "fmf.json")
			if os.path.isfile(self.cpath):
				self.contacts = self.persistant_read(self.cpath)
			if os.path.isfile(self.fpath):
				self.fmf_map = self.persistant_read(self.fpath)

		# Logger
		logging.basicConfig()
		self.logger = logging.getLogger(__name__)
		self.logger.setLevel(logging.DEBUG)
		if verbose:
			self.logger.setLevel(logging.INFO)

		self.authenticate()

	def persistant_write(self, fname, data):
		# data is a dictionary
		with open(fname, 'w') as f:
			json.dump(data, f)

	def persistant_read(self, fname):
		with open(fname, 'r') as f:
			return json.load(f)

	def update_cookies(self, r):
		self.cookies = r.cookies

	def request(self, url, method="GET", headers=None, body=None, wait_time=10):

		# requests function lookup
		functions = {
			"POST": self.http.post,
			"GET": self.http.get
		}

		r = None

		count = 0
		max_tries = 3
		exp_time = 0.0625

		# bad code practice. If LAN is down then it will hit the exception case
		# if apple server is down then itll get stuck in while loop and try with exponential backoff
		while not r:
			# just in case
			if count > max_tries:
				self.logger.info("Max tries reached")
				return None

			try:
				r = functions[method](url, headers=headers, json=body, cookies=self.cookies)
			except Exception as e:
				self.logger.debug("Error in request")
				self.logger.debug("Error: " + str(e))
				self.logger.debug("Response: " + str(r))

				r = None
				time.sleep(wait_time)
				continue

			# exponential back off
			if exp_time <= 16384: # lowest freq is ~ once per hr for apple server to come up
				exp_time *= 2
				count = 0
			count += 1
			time.sleep(exp_time)

		return r

	def get_service_url(self, resp, service):
		if resp:
			if service in resp["webservices"].keys():
				if resp["webservices"][service]["status"] == "active":
					self.logger.info("FMF service enabled on account")
					self.fmf_base_url = resp["webservices"][service]["url"]
					return
		raise FMFException("Please check that FMF is enabled on your iCloud account.")

	def get_dsid(self, resp):
		if resp:
			self.logger.info("Login succesful")
			self.dsid = resp["dsInfo"]["dsid"]
		else:
			raise FMFException("Please check that your login information is correct.")

	def authenticate(self):
		self.logger.info("Authenticating FMF service")
		auth_url = "https://setup.icloud.com/setup/ws/1/login?clientBuildNumber={0}&clientId={1}"
		auth_url = auth_url.format(self.build_id, self.client_id)

		headers = {
			"Origin": "https://www.icloud.com",
			"Referer": "https://www.icloud.com"
		}

		data = {
			"apple_id": self.aid,
			"password": self.password,
			"extended_login": False
		}

		r = self.request(auth_url, "POST", headers=headers, body=data)

		self.update_cookies(r)

		auth_resp = r.json()
		self.get_dsid(auth_resp)
		self.get_service_url(auth_resp, "fmf")

	def refresh(self, init=False):
		self.logger.info("Refresh called")
		action = "refresh"
		if init:
			action = "init"

		fmf_url = "{0}/fmipservice/client/fmfWeb/{1}Client?clientBuildNumber={2}&clientId={3}&dsid={4}"

		headers = {
			"Origin": "https://www.icloud.com",
			"Referer": "https://www.icloud.com"
		}

		data = {
			"clientContext": {
				"productType": "fmfWeb",
				"appVersion": "1.0",
				"contextApp": "com.icloud.web.fmf",
				"userInactivityTimeInMS": 1,
				"tileServer": "Apple"
			}
		}

		fmf_url = fmf_url.format(self.fmf_base_url, action, self.build_id, self.client_id, self.dsid)

		r = self.request(fmf_url, "POST", headers=headers, body=data)

		# update the cookies
		self.update_cookies(r)

		# process data
		data = r.json()

		# get contacts
		name2id = {}
		if "contactDetails" in data:
			for contact in data["contactDetails"]:
				name = contact["firstName"] + " " + contact["lastName"]
				name2id[name] = contact["id"]

		# get locations
		# k: id
		# v: [timestamp(ms), country, streetname, streetaddress, coutnrycode, locality, statecode, administrativearea]
		fmf_map = {}
		if "locations" in data:
			for location in data["locations"]:
				if location["location"]:
					timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(int(location["location"]["timestamp"])/1000))
					address = location["location"]["address"]
					if address:
						fmf_map[location["id"]] = [timestamp, address]
					continue # sometimes address isn't ready yet

		return name2id, fmf_map

	def update(self, tries=7, min_tries=2, wait_time=3):
		self.logger.info("Find called")
		if self.first_run:
			# run init first
			self.contacts, self.fmf_map = self.refresh(init=True)

		for i in range(tries):
			new_contacts, new_fmf_map = self.refresh()

			# update if anything changed in contacts
			if new_contacts != self.contacts:
				self.logger.info("Contacts are different")
				self.logger.info("Old contacts:")
				self.logger.info(self.contacts)
				self.contacts.update(new_contacts)
				self.logger.info("Updated contacts:")
				self.logger.info(self.contacts)

			self.logger.info("Updating fmf_map")
			different = False
			# check if anything changed in fmf_map
			for f in new_fmf_map:
				# checks if anything changed
				if f in self.fmf_map:
					if new_fmf_map[f][1] != self.fmf_map[f][1]:
						self.fmf_map[f] = new_fmf_map[f]
						different = True
				# new_fmf_map has something new
				else:
					self.fmf_map[f] = new_fmf_map[f]
					different = True

			# nothing changed and not the first run
			if not different and i > min_tries - 1:
				self.logger.info("nothing changed")
				break

			time.sleep(wait_time)

		# error handling
		if not self.contacts:
			self.logger.debug("Contacts is empty")
			return None
		if not self.fmf_map:
			self.logger.debug("FMF map is empty")
			return None

		if self.cache:
			self.persistant_write(self.cpath, self.contacts)
			self.persistant_write(self.fpath, self.fmf_map)

	def get_user_by_name(self, user, update=False, hook=None):
		self.logger.info("Finding user: {0}".format(user))
		if update:
			# update data
			self.update()

		# use hooks as functions to run other utilities with that information
		if user in self.contacts:
			if self.contacts[user] in self.fmf_map:
				result = self.fmf_map[self.contacts[user]]
				if hook:
					hook(user, result)
				return result
				
		self.logger.debug("User {0} not in contacts or can't be found right now".format(self.contacts[user]))
		return None

	def get_user_by_id(self, uid, update=False, reverse=True, hook=None):
		self.logger.info("Finding user id: {0}".format(uid))
		if update:
			# update data
			self.update()

		# find the user name associated with the user id
		user = None
		for u, u_id in self.contacts.iteritems():
			if u_id == uid:
				if reverse:
					user = u
				else:
					user = u_id

		if user:
			if uid in self.fmf_map:
				result = self.fmf_map[uid]
				if hook:
					hook(user, result)
				return result
				
		self.logger.debug("UserID {0} not in contacts or can't be found right now".format(uid))
		return None
