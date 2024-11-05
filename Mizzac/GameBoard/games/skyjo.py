import pandas as pd
from django.utils import timezone
from GameBoard.models import SkyJoSave

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
        # Code to import game data from Excel using pandas
        data = pd.read_excel(file_path)
        # Process the data and insert it into the database
        pass

    def other_useful_function(self):
        # Other useful functions related to SkyJo
        passclass SkyJoSave(models.Model):
    id = models.AutoField(primary_key=True)
    date_time = models.DateTimeField(auto_now_add=True)
    users = models.JSONField(default=dict, blank=False)
    scores = models.JSONField(default=dict, blank=False)
    ranking = models.JSONField(default=list, blank=True)