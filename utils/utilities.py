import os
from datetime import datetime


def log(key: str, value: str | None = None):
    if os.getenv("print") == "true":
        print(key, " : ", value)

def convert_date_to_string(date: datetime):

    return (str(date.year)+"-"+str(date.month)+"-"+str(date.hour)+" "+str(date.hour)+":"+str(date.minute))

def structurize(input_array):
    result_dict = {}

    load_type_dict = {
        "private_pool": "Private Pool",
        "open_market": "Open Market"
    }

    for item in input_array:
        bl_id = item["bl_id"]
        if bl_id not in result_dict:
            result_dict[bl_id] = {
                "bl_id": bl_id,
                "bid_time": item["bid_time"],
                "reporting_from_time": item["reporting_from_time"],
                "reporting_to_time": item["reporting_to_time"],
                "bl_cancellation_reason": item["bl_cancellation_reason"],
                "load_type": load_type_dict[item["bid_mode"]],
                "src_city": item["src_city"],
                "dest_city": item["dest_city"],
                "transporters": []  # Rename bid_items to transporters
            }

        bid_item = {
            "la_transporter_id": item["la_transporter_id"],
            "trans_pos_in_bid": item["trans_pos_in_bid"],
            "price": item["price"],
            "price_difference_percent": item["price_difference_percent"],
            "no_of_fleets_assigned": item["no_of_fleets_assigned"],
            "contact_name": item["name"],
            # "contact_name": item["contact_name"],
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
            if fleet_item not in existing_transporter["fleets"] and item["trf_active"]:
                existing_transporter["fleets"].append(fleet_item)
        else:
            # If transporter doesn't exist, add it along with the fleet
            if item["trf_active"]:
                bid_item["fleets"].append(fleet_item)
            if item["tr_active"] and item["la_active"]:
                result_dict[bl_id]["transporters"].append(bid_item)
    return list(result_dict.values())
 
def structurize_assignment_data(data):
    # Initialize a dictionary to organize data by transporter_id
    transporter_data = {}
    for entry in data:
        bid_details = entry["bid_details"]
        transporter_id = bid_details.transporter_id
        rate = bid_details.rate
        comment = bid_details.comment

        # Create or update the transporter entry
        if transporter_id not in transporter_data:
            transporter_data[transporter_id] = {
                "name": entry["transporter_name"],
                "id": transporter_id,
                "total_number_attempts": 0,
                "pmr_price": None,
                "assigned": None,
                "lowest_price": float('inf'),
                "lowest_price_comment": None,
                "rates": [],
                "fleet_assigned": None
            }

        transporter_entry = transporter_data[transporter_id]

        # Update total_number_attempts
        # transporter_entry["total_number_attempts"] += 1

        if rate < transporter_entry["lowest_price"]:
            transporter_entry["lowest_price"] = rate
            transporter_entry["lowest_price_comment"] = comment

        
        existing_entry = next((item for item in transporter_entry["rates"] if item["rate"] == rate and item["comment"] == comment), None)
        # Add rate and comment to the rates array
        if not existing_entry:
            transporter_entry["rates"].append({"rate": rate, "comment": comment})

        if not entry["load_assigned"]:
            transporter_entry["pmr_price"] = None
            transporter_entry["fleet_assigned"] = None
        elif transporter_id == entry["load_assigned"].la_transporter_id:
            transporter_entry["fleet_assigned"] = entry["load_assigned"].no_of_fleets_assigned
            transporter_entry["pmr_price"] = entry["load_assigned"].pmr_price
            transporter_entry["assigned"] = entry["load_assigned"].is_active

    # Sort the rates array for each transporter by rate
    for transporter_entry in transporter_data.values():
        transporter_entry["rates"].sort(key=lambda x: x["rate"])
        transporter_entry["total_number_attempts"] = len(transporter_entry["rates"])

    # Sort the final array by lowest_price
    sorted_transporter_data = []
    for transporter_entry in transporter_data.values():
        sorted_data_for_transporter = sorted(
            transporter_data.values(), key=lambda x: x["lowest_price"])
        if (sorted_data_for_transporter not in sorted_transporter_data):
            sorted_transporter_data.append(sorted_data_for_transporter)

    return sorted_transporter_data

def structurize_transporter_bids(bids):

    bid_details = []

    for bid_load, shipper, src_dest_pair in bids:

        bid_detail = {
            "bid_id": bid_load.bl_id,
            "shipper_name": shipper.name,
            "contact_number": shipper.contact_no,
            "src_city": src_dest_pair.src_city if src_dest_pair else None,
            "dest_city": src_dest_pair.dest_city if src_dest_pair else None,
            "bid_time": bid_load.bid_time,
            "load_status" : bid_load.load_status,
        }

        bid_details.append(bid_detail)
    
    return bid_details
