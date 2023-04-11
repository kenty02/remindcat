import dataset

db = dataset.connect('sqlite:///mydatabase.db')

table = db['reminders']
# table.insert(dict(name='John Doe', age=37))
# table.insert(dict(name='Jane Doe', age=34, gender='female'))

# john = table.find_one(name='John Doe')
