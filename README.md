```python
class User:
        def __init__(self,name,age,pronouns):
            self.name = name
            self.age = age
            self.pronouns = pronouns
        def introduce(self):
            print (f'Hello my name is {self.name}, im {self.age} year(s) old and my pronouns are {self.pronouns}.')

alden5 = User('Alden',17,'(he/him)')
alden5.introduce()
```
