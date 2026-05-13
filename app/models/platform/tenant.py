# from sqlalchemy import Column, Integer, String, ForeignKey
# from app.db.base import Base


# class Tenant(Base):
#     __tablename__ = "tenants"

#     id = Column(Integer, primary_key=True)
#     name = Column(String, nullable=False)
#     slug = Column(String, unique=True)

#     owner_id = Column(Integer, ForeignKey("users.id"))