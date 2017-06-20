from google.appengine.ext import ndb


class States(ndb.Model):
    working = ndb.BooleanProperty(default=False)
    updated_at = ndb.DateTimeProperty(auto_now=True)
    created_at = ndb.DateTimeProperty(auto_now_add=True)
