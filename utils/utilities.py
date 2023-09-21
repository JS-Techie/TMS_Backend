import os
from datetime import datetime
from collections import defaultdict


def log(key: str, value: str | None = None):
    if os.getenv("print") == "true":
        print(key, " : ", value)


def convert_date_to_string(date: datetime):

    return (str(date.year)+"-"+str(date.month)+"-"+str(date.hour)+" "+str(date.hour)+":"+str(date.minute))


def structurize(input_array):
    result_dict = {}

 

    for item in input_array:
        bl_id = item["bl_id"]
        if bl_id not in result_dict:
            result_dict[bl_id] = {
                "bl_id": bl_id,
                "bid_time": item["bid_time"],
                "reporting_from_time": item["reporting_from_time"],
                "reporting_to_time": item["reporting_to_time"],
                "bl_cancellation_reason": item["bl_cancellation_reason"],
                "load_type": item["load_type"],
                "transporters": []  # Rename bid_items to transporters
            }

 

        bid_item = {
            "la_transporter_id": item["la_transporter_id"],
            "trans_pos_in_bid": item["trans_pos_in_bid"],
            "price": item["price"],
            "price_difference_percent": item["price_difference_percent"],
            "no_of_fleets_assigned": item["no_of_fleets_assigned"],
            "name": item["name"],
            "contact_name": item["contact_name"],
            "contact_no": item["contact_no"],
            "fleets": []  # Initialize an empty list for fleets
        }

 
        fleet_item = {
            "tf_id": item["tf_id"],
            "fleet_no": item["fleet_no"],
            "src_addrs": item["src_addrs"],
            "dest_addrs": item["dest_addrs"]
        }

 

        # Check if a transporter with the same la_transporter_id already exists
        existing_transporters = [
            transporter for transporter in result_dict[bl_id]["transporters"]
            if transporter["la_transporter_id"] == bid_item["la_transporter_id"]
        ]

 

        if existing_transporters:
            # If transporter exists, append the fleet to its fleets list
            existing_transporter = existing_transporters[0]
            if not fleet_item in existing_transporter["fleets"] and item["trf_active"]:
                existing_transporter["fleets"].append(fleet_item)
        else:
            # If transporter doesn't exist, add it along with the fleet
            if item["trf_active"]:
                bid_item["fleets"].append(fleet_item)
            if item["tr_active"] and item["la_active"]:
                result_dict[bl_id]["transporters"].append(bid_item)

 

    return list(result_dict.values())