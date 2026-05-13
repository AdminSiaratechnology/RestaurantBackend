# from sqlalchemy import Column, Integer, String, Boolean
# from app.db.base import Base


# class PlatformUser(Base):
#     __tablename__ = "platform_users"

#     id = Column(Integer, primary_key=True)
#     name = Column(String)
#     email = Column(String, unique=True)
#     password_hash = Column(String)
#     role = Column(String, default="SUPER_ADMIN")
#     is_active = Column(Boolean, default=True)