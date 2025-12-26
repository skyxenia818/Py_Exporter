from pydantic import BaseModel

class BaseCollector(BaseModel):
    def collect(self):
        pass