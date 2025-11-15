from pydantic import BaseModel

class Register(BaseModel):
    name : str
    email : str
    password : str

class OTPVerify(BaseModel):
    otp : str
    session_id : str

class Login(BaseModel):
    email : str
    password : str
    
class ResetPassword(BaseModel):
    email: str
    otp: str
    new_password: str

class EmailOnlyRequest(BaseModel):
    email: str