import json
import os
from config import logger
from DataManagement import json_directory


def initialize_users_file():
    """Creates users.json if it doesn't exist"""
    try:
        json_dir = json_directory()
        file_path = os.path.join(json_dir, 'users.json')
        if not os.path.exists(file_path):
            logger.info("Creating new users.json file")
            default_structure = {
                "users": []
            }
            with open(file_path, 'w') as f:
                json.dump(default_structure, f, indent=4)
            logger.info("users.json created successfully")
    except Exception as e:
        logger.error(f"Error creating users.json: {str(e)}", exc_info=True)
        raise

def check_login(username, password):
    """function for checking login credentials"""
    logger.debug(f"Checking login for user: {username}")
    initialize_users_file()

    try:
        json_dir = json_directory()
        file_path = os.path.join(json_dir, 'users.json')
        with open(file_path, 'r') as f:
            users_file = json.load(f)

        users_file = users_file.get('users')
        for user_dict in users_file:
            if username.upper() == user_dict.get('username').upper():
                if password == user_dict.get('password'):
                    is_google = user_dict.get('is_google_user', False)
                    login_type = "Google" if is_google else "regular"
                    logger.info(f"Successful {login_type} login for user: {username}")
                    return True
                else:
                    logger.warning(f"Failed login attempt for user: {username} - Invalid password")
                    return False
        
        logger.warning(f"Failed login attempt - User not found: {username}")
        return False
            
    except Exception as e:
        logger.error(f"Error in check_login: {str(e)}", exc_info=True)
        return False

def check_username_avaliability(username):
    """Check if the username is free before new registration"""
    logger.debug(f"Checking availability for username: {username}")
    initialize_users_file()

    try:
        json_dir = json_directory()
        file_path = os.path.join(json_dir, 'users.json')
        with open(file_path, 'r') as f:
            users_file = json.load(f)

        users_file = users_file.get('users')
        for user_dict in users_file:
            if user_dict.get('username').upper() == username.upper():
                logger.debug(f"Username '{username}' already exists")
                return False

        logger.debug(f"Username '{username}' is available")
        return True
    except Exception as e:
        logger.error(f"Error checking username availability: {str(e)}", exc_info=True)
        return False

def registration(username, password, full_name=None, is_google_user=False, profile_picture=None):
    """function for register new username"""
    initialize_users_file()

    try:
        if check_username_avaliability(username):
            NewUser = {
                'username': username.lower(),
                'password': password,
                'full_name': full_name,
                'is_google_user': is_google_user,
                'profile_picture': profile_picture
            }

            json_dir = json_directory()
            file_path = os.path.join(json_dir, 'users.json')
            with open(file_path, 'r') as f:
                users_file = json.load(f)

            users_file['users'].append(NewUser)

            with open(file_path, 'w') as f:
                json.dump(users_file, f, indent=4)
            
            user_type = "Google" if is_google_user else "regular"
            logger.info(f"New {user_type} user registered: {username}")
        else:
            # If user exists and it's a Google login attempt, log appropriately
            json_dir = json_directory()
            file_path = os.path.join(json_dir, 'users.json')
            with open(file_path, 'r') as f:
                users_file = json.load(f)
            
            for user in users_file.get('users', []):
                if user.get('username').lower() == username.lower():
                    if is_google_user:
                        logger.info(f"Existing Google user logged in: {username}")
                    else:
                        logger.info(f"User already exists: {username}")
                    break
                    
    except Exception as e:
        logger.error(f"Error during registration: {str(e)}", exc_info=True)
        raise