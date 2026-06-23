from sqlalchemy import select
from app.accounts.branch.model import Branch
from app.accounts.staff.model import Staff


async def get_staff_all_branches(db, client_id: int):

    # 1. get branches
    branches_result = await db.execute(
        select(Branch).where(Branch.client_id == client_id)
    )
    branches = branches_result.scalars().all()

    branch_ids = [b.id for b in branches]

    if not branch_ids:
        return {
            "total_staff": 0,
            "branches": []
        }

    # 2. get all staff
    staff_result = await db.execute(
        select(Staff).where(Staff.branch_id.in_(branch_ids))
    )
    staff_list = staff_result.scalars().all()

    response = {
        "total_staff": len(staff_list),
        "branches": []
    }

    # 3. group by branch
    for branch in branches:

        branch_staff = [
            s for s in staff_list
            if s.branch_id == branch.id
        ]

        response["branches"].append({
            "branch_id": branch.id,
            "branch_name": branch.name,
            "total_staff": len(branch_staff),

            "staff": [
                {
                    "id": s.id,
                    "name": s.name,
                    "email": s.email,
                    "role": s.role.value if hasattr(s.role, "value") else s.role,
                    "phone_number": s.phone_number,
                    "is_active": s.is_active,

                    "city": s.city,
                    "state": s.state,
                    "pincode": s.pincode,

                    "monthly_salary": s.monthly_salary,
                    "hourly_rate": s.hourly_rate,
                }
                for s in branch_staff
            ]
        })

    return response