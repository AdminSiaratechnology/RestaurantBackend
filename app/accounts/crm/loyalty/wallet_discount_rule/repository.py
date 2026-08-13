# from sqlalchemy.orm import Session

# from .model import WalletDiscountRule


# class WalletDiscountRuleRepository:

#     # ========================================================
#     # GET BY BRANCH
#     # ========================================================

#     @staticmethod
#     def get_by_branch(
#         db: Session,
#         *,
#         client_id: int,
#         branch_id: int,
#         active_only: bool = False,
#     ) -> WalletDiscountRule | None:

#         query = (
#             db.query(WalletDiscountRule)
#             .filter(
#                 WalletDiscountRule.client_id == client_id,
#                 WalletDiscountRule.branch_id == branch_id,
#             )
#         )

#         if active_only:
#             query = query.filter(
#                 WalletDiscountRule.is_active.is_(True)
#             )

#         return query.first()

#     # ========================================================
#     # CREATE
#     # ========================================================

#     @staticmethod
#     def create(
#         db: Session,
#         *,
#         client_id: int,
#         branch_id: int,
#         max_wallet_discount_percent: float,
#         is_active: bool,
#     ) -> WalletDiscountRule:

#         rule = WalletDiscountRule(
#             client_id=client_id,
#             branch_id=branch_id,
#             max_wallet_discount_percent=(
#                 max_wallet_discount_percent
#             ),
#             is_active=is_active,
#         )

#         db.add(rule)

#         try:
#             db.commit()
#             db.refresh(rule)

#         except Exception:
#             db.rollback()
#             raise

#         return rule

#     # ========================================================
#     # UPDATE
#     # ========================================================

#     @staticmethod
#     def update(
#         db: Session,
#         *,
#         rule: WalletDiscountRule,
#         max_wallet_discount_percent: float | None = None,
#         is_active: bool | None = None,
#     ) -> WalletDiscountRule:

#         if max_wallet_discount_percent is not None:
#             rule.max_wallet_discount_percent = (
#                 max_wallet_discount_percent
#             )

#         if is_active is not None:
#             rule.is_active = is_active

#         try:
#             db.commit()
#             db.refresh(rule)

#         except Exception:
#             db.rollback()
#             raise

#         return rule

#     # ========================================================
#     # DEACTIVATE
#     # ========================================================

#     @staticmethod
#     def deactivate(
#         db: Session,
#         *,
#         rule: WalletDiscountRule,
#     ) -> WalletDiscountRule:

#         rule.is_active = False

#         try:
#             db.commit()
#             db.refresh(rule)

#         except Exception:
#             db.rollback()
#             raise

#         return rule