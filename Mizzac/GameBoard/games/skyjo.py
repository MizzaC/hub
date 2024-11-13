import pandas as pd
from django.utils import timezone
from GameBoard.models import SkyJoSave
import json

class SkyJo:
    def __init__(self, db_name):
        self.db_name = db_name

    def insert_data(self, data):
        
        # Create a new SkyJoSave instance
        new_game = SkyJoSave(
            date_time=timezone.now(),
            users=data.get('users', {}),
            scores=data.get('scores', {}),
            ranking=data.get('ranking', [])
        )

        # Save the instance to the database
        new_game.save()
        
        pass

    def update_data(self, data):
        # Code to update data in the database
        pass

    def delete_data(self, data):
        # Code to delete data from the database
        pass

    def get_data(self):
        # Code to retrieve data from the database
        pass

    def import_data_from_excel(self, file_path):
        """
        Imports data from an Excel file and processes it into a dictionary format for database insertion.
        The Excel file is expected to have the following structure:
        - The first row contains headers, where the first column is 'Tours/Joueurs' and the subsequent columns are user names.
        - The first column contains the round numbers.
        - The subsequent columns contain the scores for each user in each round.
        Example of the expected Excel table:
        Tours/Joueurs | user1 | user2 | user3 | user4
        1             |  10   |  20   |  30   |  40
        2             |  20   |  30   |  40   |  50
        3             |  30   |  40   |  50   |  60
        Parameters:
        file_path (str): The path to the Excel file to be imported.
        Returns:
        None
        The method processes the data and converts it into a dictionary with the following structure:
        {
            'users': [list of user names],
            'scores': {user_name: [list of scores]},
            'ranking': [list of user names sorted by total score]
        }
        The resulting dictionary is then inserted into the database using the `insert_data` method.
        """
        
        data = pd.read_excel(file_path)
        
        # Assuming the first row contains the headers
        headers = data.columns.tolist()
        users = headers[1:]  # Skip the first column which is 'Tours/Joueurs'
        
        scores = {}
        for user in users:
            scores[user] = data[user].tolist()
        
        # Sort users by total score in ascending order (smallest score first)
        ranking = sorted(scores.items(), key=lambda item: sum(item[1]))
        
        data_dict = {
            'users': users,
            'scores': scores,
            'ranking': [user for user, _ in ranking]
        }
        
        self.insert_data(data_dict)
        
    
    def import_data_from_json(self, file_path):
        """
        Imports data from a JSON file containing multiple game scores.
        The JSON file should contain a list of game data with the same structure:
        [
            {
                "users": ["user1", "user2", "user3"],
                "scores": {
                    "user1": [10, 20, 30],
                    "user2": [15, 25, 35],
                    "user3": [5, 15, 25]
                }
            },
            ...
        ]
        """
        
        with open(file_path, 'r') as file:
            games_data = json.load(file)
        
        # Process each game in the JSON file
        for game_data in games_data:
            users = game_data.get('users', [])
            scores = game_data.get('scores', {})
            
            # Calculate ranking based on total scores
            ranking = sorted(scores.items(), key=lambda item: sum(item[1]))
            
            data_dict = {
                'users': users,
                'scores': scores,
                'ranking': [user for user, _ in ranking]
            }
            
            self.insert_data(data_dict)
    
    def export_data_from_json(self, file_path):
        # Code to import game data from Excel using pandas
        data = pd.read_excel(file_path)
        # Process the data and insert it into the database
        pass

    def other_useful_function(self):
        # Other useful functions related to SkyJo
        pass