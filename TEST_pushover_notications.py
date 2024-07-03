import requests

def send_pushover_notification(user_key, api_token, message, title=None, priority=None):
    """
    Send a push notification via Pushover API.
    
    :param user_key: User's Pushover user key
    :param api_token: Your Pushover application API token
    :param message: Notification message
    :param title: Notification title (optional)
    :param priority: Notification priority (optional)
    """
    url = 'https://api.pushover.net/1/messages.json'
    
    data = {
        'token': api_token,
        'user': user_key,
        'message': message,
        'title': title,
        'priority': priority
    }
    
    response = requests.post(url, data=data)
    
    if response.status_code == 200:
        print("Notification sent successfully.")
    else:
        print("Failed to send notification. Error:", response.text)

# Replace with your Pushover user key and application API token
user_key = 'u4hrgnxo4bbxd7iuitioycrtkesqu9'
api_token = 'arx76h1enfka4rg77kr8pjst7dbza4'

# Send a test notification
send_pushover_notification(user_key, api_token, "This is a test notification from Python.")
