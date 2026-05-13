
# from sqlalchemy import select
# from app.accounts.client.model import Client
# from app.accounts.partner.model import Partner
# from app.accounts.staff.model import Staff
# from app.accounts.superadmin.model import SuperAdmin
# from app.accounts.deps import UserRole
# from passlib.context import CryptContext
# from app.accounts.auth.utils import create_access_token

# pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# async def authenticate_user(db, email, password):
#     models = [
#         (SuperAdmin, UserRole.SUPER_ADMIN),
#         (Partner, UserRole.PARTNER),
#         (Client, UserRole.CLIENT),
#         (Staff, UserRole.STAFF),
#     ]

#     for model, role in models:
#         result = await db.execute(select(model).where(model.email == email))
#         user = result.scalar_one_or_none()

#         if user:
#             if not pwd_context.verify(password, user.password_hash):
#                 return None

#             token = create_access_token({
#                 "user_id": user.id,
#                 "role": role,
#                 "client_id": getattr(user, "client_id", None)
#             })

#             return token, role

#     return None
