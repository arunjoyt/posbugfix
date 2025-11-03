import frappe
from frappe.utils import cint
from frappe.utils.nestedset import get_root_of
from erpnext.accounts.doctype.pos_invoice.pos_invoice import get_stock_availability
from erpnext.stock.get_item_details import get_conversion_factor
from erpnext.selling.page.point_of_sale.point_of_sale import (
    search_by_term,
    get_conditions,
    get_item_group_condition,
    filter_result_items,
)

@frappe.whitelist()
def get_items(start, page_length, price_list, item_group, pos_profile, search_term=""):
    warehouse, hide_unavailable_items = frappe.db.get_value(
        "POS Profile", pos_profile, ["warehouse", "hide_unavailable_items"]
    )

    result = []

    if search_term:
        result = search_by_term(search_term, warehouse, price_list) or []
        filter_result_items(result, pos_profile)
        if result:
            return result

    if not frappe.db.exists("Item Group", item_group):
        item_group = get_root_of("Item Group")

    condition = get_conditions(search_term)
    condition += get_item_group_condition(pos_profile)

    lft, rgt = frappe.db.get_value("Item Group", item_group, ["lft", "rgt"])

    bin_join_selection, bin_join_condition = "", ""
    if hide_unavailable_items:
        bin_join_selection = "LEFT JOIN `tabBin` bin ON bin.item_code = item.name"
        bin_join_condition = "AND (item.is_stock_item = 0 OR (item.is_stock_item = 1 AND bin.warehouse = %(warehouse)s AND bin.actual_qty > 0))"

    items_data = frappe.db.sql(
        """
		SELECT
			item.name AS item_code,
			item.item_name,
			item.description,
			item.stock_uom,
			item.image AS item_image,
			item.is_stock_item,
			item.sales_uom
		FROM
			`tabItem` item {bin_join_selection}
		WHERE
			item.disabled = 0
			AND item.has_variants = 0
			AND item.is_sales_item = 1
			AND item.is_fixed_asset = 0
			AND item.item_group in (SELECT name FROM `tabItem Group` WHERE lft >= {lft} AND rgt <= {rgt})
			AND {condition}
			{bin_join_condition}
		ORDER BY
			item.name asc
		LIMIT
			{page_length} offset {start}""".format(
            start=cint(start),
            page_length=cint(page_length),
            lft=cint(lft),
            rgt=cint(rgt),
            condition=condition,
            bin_join_selection=bin_join_selection,
            bin_join_condition=bin_join_condition,
        ),
        {"warehouse": warehouse},
        as_dict=1,
    )

    # return (empty) list if there are no results
    if not items_data:
        return result

    current_date = frappe.utils.today()

    for item in items_data:
        item.actual_qty, _ = get_stock_availability(item.item_code, warehouse)

        # Bug:
        # Current behavior:
        #   code: "valid_upto": ["in", [None, "", current_date]],
	    #   Works only if valid_upto is empty or exactly equal to current_date.
        #   Fails when valid_upto is after (> than) current_date — meaning valid prices with a future expiry date are ignored.        # Expected behavior:
        # Expected behavior:
        #   Include all records where:
        #   (valid_upto IS NULL OR valid_upto = "" OR valid_upto >= current_date)
        #   So if valid_upto is in the future, the price should still be valid.
        # Solution:
        #   Use COALESCE function on valid_upto
        #
        #
        # item_prices = frappe.get_all(
        # 	"Item Price",
        # 	fields=["price_list_rate", "currency", "uom", "batch_no", "valid_from", "valid_upto"],
        # 	filters={
        # 		"price_list": price_list,
        # 		"item_code": item.item_code,
        # 		"selling": True,
        # 		"valid_from": ["<=", current_date],
        # 		"valid_upto": ["in", [None, "", current_date]],
        # 	},
        # 	order_by="valid_from desc",
        # )

        item_prices = frappe.db.sql(
            """
			SELECT 
				price_list_rate, currency, uom, batch_no, valid_from, valid_upto
			FROM
				`tabItem Price`
			WHERE
				price_list = %(price_list)s 
				AND item_code = %(item_code)s
				AND selling = 1
				AND valid_from <= %(current_date)s
				AND COALESCE(valid_upto, %(current_date)s) >= %(current_date)s
			ORDER BY 
				valid_from DESC
			""",
            {
                "price_list": price_list,
                "item_code": item.item_code,
                "current_date": current_date,
            },
            as_dict=True,
        )

        stock_uom_price = next(
            (d for d in item_prices if d.get("uom") == item.stock_uom), {}
        )
        item_uom = item.stock_uom
        item_uom_price = stock_uom_price

        if item.sales_uom and item.sales_uom != item.stock_uom:
            item_uom = item.sales_uom
            sales_uom_price = next(
                (d for d in item_prices if d.get("uom") == item.sales_uom), {}
            )
            if sales_uom_price:
                item_uom_price = sales_uom_price

        if item_prices and not item_uom_price:
            item_uom = item_prices[0].get("uom")
            item_uom_price = item_prices[0]

        item_conversion_factor = get_conversion_factor(item.item_code, item_uom).get(
            "conversion_factor"
        )

        if item.stock_uom != item_uom:
            item.actual_qty = item.actual_qty // item_conversion_factor

        if item_uom_price and item_uom != item_uom_price.get("uom"):
            item_uom_price.price_list_rate = (
                item_uom_price.price_list_rate * item_conversion_factor
            )

        result.append(
            {
                **item,
                "price_list_rate": item_uom_price.get("price_list_rate"),
                "currency": item_uom_price.get("currency"),
                "uom": item_uom,
                "batch_no": item_uom_price.get("batch_no"),
            }
        )

    return {"items": result}
