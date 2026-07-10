# import asyncio
# import asyncpg
# import ssl

# ssl_context = ssl.create_default_context()
# ssl_context.check_hostname = False
# ssl_context.verify_mode = ssl.CERT_NONE

# async def main():
#     conn = await asyncpg.connect(
#         user="restaurant_management_v2_l9oc_user",
#         password="s4W1XfOjwaebq688BMAr3gmNSwVhhMb2",
#         database="restaurant_management_v2_l9oc",
#         host="dpg-d8f6kf42m8qs73dtbnag-a.oregon-postgres.render.com",
#         ssl=ssl_context,
#     )

#     print("CONNECTED")
#     await conn.close()

# asyncio.run(main())

import asyncio
import asyncpg

async def main():
    conn = await asyncpg.connect(
        "postgresql://restaurant_management_v2_kaf1_user:cUj2djaVaY82ASlfTwoBIEjpyaRtCev0@dpg-d98942favr4c7394p6cg-a.oregon-postgres.render.com/restaurant_management_v2_kaf1",
        ssl="require",
        timeout=30,
    )

    print("CONNECTED")
    await conn.close()

asyncio.run(main())