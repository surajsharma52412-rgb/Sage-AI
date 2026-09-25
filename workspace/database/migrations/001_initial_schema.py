from sqlalchemy import create_engine, Column, Integer, String, Date, TIMESTAMP, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), default='user')
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    applications = relationship("Application", back_populates="user")

class Application(Base):
    __tablename__ = 'applications'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    date_of_birth = Column(Date, nullable=False)
    application_date = Column(TIMESTAMP, default=datetime.utcnow)
    status = Column(String(50), default='pending')
    user = relationship("User", back_populates="applications")
    statuses = relationship("Status", back_populates="application")

class Status(Base):
    __tablename__ = 'status'
    id = Column(Integer, primary_key=True)
    application_id = Column(Integer, ForeignKey('applications.id'), nullable=False)
    status = Column(String(50), nullable=False)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow)
    application = relationship("Application", back_populates="statuses")
