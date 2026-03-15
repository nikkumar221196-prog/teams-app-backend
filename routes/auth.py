from fastapi import APIRouter
from pydantic import BaseModel
import database

router = APIRouter()

class UserLogin(BaseModel):
    name: str
    organization: str

@router.post("/login")
def login(user: UserLogin):
    name = user.name.strip()
    organization = user.organization.strip()
    
    if not name:
        return {"error": "Name is required"}
    if not organization:
        return {"error": "Organization is required"}
    
    # Add user to database (will ignore if already exists)
    database.add_user(name, organization)
    
    return {"success": True, "user": {"name": name, "organization": organization}}

@router.get("/users/{organization}")
def get_users(organization: str):
    return database.get_users_by_org(organization)
