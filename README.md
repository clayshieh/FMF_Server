# FMF_Server
FindMyFriends API intended to be used for server side applications written using requests and iCloud.com

### Prerequisites
The only non standard Python Library you need is requests which you can install by running

`pip install requests`


### Getting Started
Import FMF into your Python file by including the following line 

`import FMF`

### Usage
Initialize the client with your apple ID login which should be your email and password.

`f = FMF("fmf@example.com", "password")`

When you want to refresh the location status of all your Find My Friend contacts, call the `update()` method

`f.update()`

You can also specify the number of minimum attempts (to get a more accurate reading), the maximum number of attempts (to prevent significant delays) and the wait time (in seconds) between each attempt to avoid spamming Apple servers. The default settings that I've personally found to be good enough are as follows: 2 minimum attempts, 7 maximum attempts and a 3 second wait time.

When you want to get the location data of a contact use the `get_user_by_name()` method with the contact's **contact name as it appears in your contacts**.

`f.get_user_by_name("Best Friend")`

the api currently does not play well with contacts with emoji's in the name so an alternative method to find the contact is provided, `get_user_by_id()`.

`f.get_user_by_id("~QLKSDFKL8.DK")`

You can also specify a function with the optional `hook` argument to do something with the user's name and the returned data. For example if you are using a SMS Api that has a `text()` function, if you set `hook=text` then it will execute `text(user, result)` where user is the contact name of the person you are trying to find and result is the data of said user's current location information.

### Notes
  * Whenever the script authenticates the iCloud login, the script will trigger Apple to send you an email that a device has logged into your iCloud. I believe Apple has implemented a cookie/session variable system to remember devices that log into iCloud. Currently this API does not have the functionality to remember said cookie, store it, and reuse the cookie whenever authenticate is called so if you call authenticate n times you will receive n emails from Apple. Apple does not require you to take any actions to confirm the identity of the device so it does not affect the functionality of the API. 
  * This API does **NOT** work when 2FA is enabled on the icloud account.

### Acknowledgements
I initially referenced Vladimir Smirnov's iCloud API for general iCloud workflow and cookie implementation which can be found here

https://github.com/mindcollapse/iCloud-API/

I have sinced changed the code significantly for my own use and changed to using requests instead of httplib2 as it is better supported. Thanks!


### Contributing
Pull requests and contributions are welcomed!

### Support
For any questions or concerns, please create an issue or contact me.
