import os
import json
from flask import jsonify
from config import logger , Config



def json_directory():
    json_dir = Config.JSON_DIRECTORY
    if not os.path.exists(json_dir):
        os.makedirs(json_dir)
    return json_dir


def load_domains(username):
    try:
        json_dir = json_directory()
        file_path = os.path.join(json_dir, f'{username}_domains.json')
        if not os.path.exists(file_path):
            with open(file_path, 'w') as f:
                json.dump({"domains":[]}, f)

        with open(file_path, 'r') as f:
            data = json.load(f)
        return data.get("domains")
    except Exception as e:
        return jsonify({'message': 'An error occurred while checking domains.', 'error': str(e)}), 500
    

def add_domains(domains, username):
    try:
        current_domains=load_domains(username)
        current_domains.append(domains)
        return True
    except Exception as e:
        return jsonify({'message': 'An error occurred while adding domains.', 'error': str(e)})
    
def remove_domain(domain_to_remove, username):
    try:
        json_dir = json_directory()
        file_path = os.path.join(json_dir, f'{username}_domains.json')
        domains = load_domains(username)
        domain_found=False
        
        for i in range(len(domains)):
            if domains[i]['url'] == domain_to_remove:
                del domains[i]
                domain_found=True
                break

        if domain_found:
            with open(file_path, 'w') as f:
                json.dump({"domains": domains}, f, indent=4)
            return True
        else:     
            return False
    except Exception as e:
        return jsonify({'message': 'An error occurred while removing the domain.', 'error': str(e)})

    

def update_domains(domains, username):
    try:
        json_dir = json_directory()
        file_path = os.path.join(json_dir, f'{username}_domains.json')
        # Load current domains
        current_domains = load_domains(username)
        
        # Update or add new domains
        for domain in domains:
            # Check if domain already exists
            existing_domain = next((d for d in current_domains if d['url'] == domain['url']), None)
            
            if existing_domain:
                # Update existing domain
                existing_domain.update(domain)
            else:
                # Add new domain
                current_domains.append(domain)
        
        # Write updated domains back to file
        with open(file_path, 'w') as f:
            json.dump({"domains": current_domains}, f, indent=4)
        
        return True
    except Exception as e:
        logger.error(f"Error updating domains: {e}")
        return False
    

    
# schedular data management

def load_user_tasks(username):
    """Charge les tâches planifiées d'un utilisateur depuis un fichier JSON."""
    json_dir = json_directory()
    filepath = os.path.join(json_dir, f"{username}_tasks.json")
    if os.path.exists(filepath):
        with open(filepath, "r") as file:
            return json.load(file)
    return {"tasks": []}

def save_user_tasks(username, tasks):
    """Sauvegarde les tâches planifiées d'un utilisateur dans un fichier JSON."""
    json_dir = json_directory()
    filepath = os.path.join(json_dir, f"{username}_tasks.json")
    with open(filepath, "w") as file:
        json.dump({"tasks": tasks}, file, indent=4)

def update_user_task(username, new_task):
    """Update a user's task with improved state management"""
    try:
        json_dir = json_directory()
        file_path = os.path.join(json_dir, f"{username}_tasks.json")
        
        # Load existing tasks or create new structure
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                tasks_data = json.load(f)
        else:
            tasks_data = {"tasks": []}

        # Remove any existing task with the same job_id
        tasks_data["tasks"] = [task for task in tasks_data["tasks"] 
                             if task.get("job_id") != new_task["job_id"]]
        
        # Add the new task
        tasks_data["tasks"].append(new_task)
        
        # Save updated tasks
        with open(file_path, 'w') as f:
            json.dump(tasks_data, f, indent=4)
            
        logger.info(f"Successfully updated task for {username}: {new_task}")
        return True
    except Exception as e:
        logger.error(f"Error updating task for {username}: {str(e)}")
        return False

def delete_user_task(username):
    """Supprime une tâche planifiée d'un utilisateur."""
    #tasks_data = load_user_tasks(username)
    #tasks = tasks_data.get("tasks", [])    
    tasks = []
    logger.debug(tasks)
    save_user_tasks(username, tasks)
