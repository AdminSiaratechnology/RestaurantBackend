TEMPLATES = {
    "menu": {
        "Menu_Items": [
            {
                "Name": "Veg Burger",
                "Category": "Fast Food",
                "Branch Code": "BR001",
                "Food Type": "veg",
                "Image": "veg_burger.jpg",
                "Active": True
            }
        ],

        "Pricing": [
            {
                "Menu Item": "Veg Burger",
                "Branch Code": "BR001",
                "Price": 120,
                "Cost Price": 70,
                "Discount": 10,
                "Tax": 5,
                "CGST": 2.5,
                "SGST": 2.5,
                "Calories": 350,
                "Active": True
            }
        ],

        "BOM": [
            {
                "Menu Item": "Veg Burger",
                "Branch Code": "BR001",
                "Inventory Item": "Burger Bun",
                "Godown": "Main Store",
                "Quantity": 1
            },
            {
                "Menu Item": "Veg Burger",
                "Branch Code": "BR001",
                "Inventory Item": "Veg Patty",
                "Godown": "Main Store",
                "Quantity": 1
            },
            {
                "Menu Item": "Veg Burger",
                "Branch Code": "BR001",
                "Inventory Item": "Mayonnaise",
                "Godown": "Main Store",
                "Quantity": 20
            },
            {
                "Menu Item": "Veg Burger",
                "Branch Code": "BR001",
                "Inventory Item": "Lettuce",
                "Godown": "Main Store",
                "Quantity": 15
            }
        ]
    },
    "bill": {
        "Bills": [
            {
                "Invoice No": "INV-2025-001",
                "Branch Code": "BR001",
                "Order Type": "dine_in",
                "Customer Name": "John Doe",
                "Customer Phone": "9876543210",
                "Payment Status": "paid",        # pending / paid / partial
                "Payment Method": "cash",
                "Subtotal": 240.0,
                "CGST %": 2.5,
                "CGST Amount": 6.0,
                "SGST %": 2.5,
                "SGST Amount": 6.0,
                "Service Charge %": 5.0,
                "Service Charge Amount": 12.0,
                "Tax Total": 12.0,
                "Discount Amount": 10.0,
                "Round Off Amount": 0.5,
                "Grand Total": 254.5,
                "Paid Amount": 254.5,
                "Due Amount": 0.0,
                "Offer Discount": 0.0,
                "Final Amount": 254.5,
                "Notes": "Extra napkins requested",
                "Footer Message": "Thank you for dining with us!",
                "Billed At": "2025-06-27 13:00:00",
            }
        ]
    }
    
}