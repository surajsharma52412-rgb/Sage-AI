from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from . import models, schemas, crud
from .dependencies import get_db

router = APIRouter()

@router.post("/auth/register/", response_model=schemas.User)
def register_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = crud.get_user_by_email(db, email=user.email)
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    return crud.create_user(db=db, user=user)

@router.post("/auth/login/", response_model=schemas.Token)
def login_user(user: schemas.UserLogin, db: Session = Depends(get_db)):
    db_user = crud.authenticate_user(db, email=user.email, password=user.password)
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = crud.create_access_token(data={"sub": db_user.email})
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/applications/", response_model=schemas.Application)
def create_application(application: schemas.ApplicationCreate, db: Session = Depends(get_db)):
    return crud.create_application(db=db, application=application)

@router.get("/applications/", response_model=List[schemas.Application])
def read_applications(skip: int = 0, limit: int = 10, db: Session = Depends(get_db)):
    applications = crud.get_applications(db, skip=skip, limit=limit)
    return applications

@router.get("/applications/{application_id}", response_model=schemas.Application)
def read_application(application_id: int, db: Session = Depends(get_db)):
    db_application = crud.get_application(db, application_id=application_id)
    if db_application is None:
        raise HTTPException(status_code=404, detail="Application not found")
    return db_application

@router.put("/applications/{application_id}", response_model=schemas.Application)
def update_application(application_id: int, application: schemas.ApplicationUpdate, db: Session = Depends(get_db)):
    db_application = crud.update_application(db, application_id=application_id, application=application)
    if db_application is None:
        raise HTTPException(status_code=404, detail="Application not found")
    return db_application

@router.delete("/applications/{application_id}", response_model=schemas.Application)
def delete_application(application_id: int, db: Session = Depends(get_db)):
    db_application = crud.delete_application(db, application_id=application_id)
    if db_application is None:
        raise HTTPException(status_code=404, detail="Application not found")
    return db_application

@router.get("/status/{application_id}", response_model=schemas.Status)
def read_status(application_id: int, db: Session = Depends(get_db)):
    db_status = crud.get_status(db, application_id=application_id)
    if db_status is None:
        raise HTTPException(status_code=404, detail="Status not found")
    return db_status
