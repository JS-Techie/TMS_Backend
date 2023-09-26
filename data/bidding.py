valid_load_status = ['draft', 'not_started', 'live', 'pending',
                     'partially_confirmed', 'confirmed', 'completed', 'cancelled']
valid_rebid_status = ['not_started', 'pending',
                      'partially_confirmed', 'confirmed']
valid_cancel_status = ['draft', 'not_started',
                       'pending', 'partially_confirmed', 'confirmed']
valid_assignment_status = ['pending', 'partially_confirmed']

valid_bid_status = ['live','not_started']

status_wise_fetch_query="""
            SELECT
                t_bidding_load.bl_id,
                t_bidding_load.bid_time,
                t_bidding_load.reporting_from_time,
                t_bidding_load.reporting_to_time,
                t_bidding_load.bid_mode,
                t_bidding_load.bl_cancellation_reason,
                t_map_load_src_dest_pair.src_city,
                t_map_load_src_dest_pair.dest_city,
                t_load_assigned.la_transporter_id,
                t_load_assigned.trans_pos_in_bid,
                t_load_assigned.price,
                t_load_assigned.price_difference_percent,
                t_load_assigned.no_of_fleets_assigned,
                t_transporter.name,
                t_transporter.contact_no,
                t_tracking_fleet.tf_id,
                t_tracking_fleet.fleet_no,
                t_tracking_fleet.src_addrs,
                t_tracking_fleet.dest_addrs,
                t_load_assigned.is_active as la_active,
                t_transporter.is_active as tr_active,
                t_tracking_fleet.is_active as trf_active
            FROM t_bidding_load
            LEFT JOIN t_load_assigned ON t_load_assigned.la_bidding_load_id = t_bidding_load.bl_id
            LEFT JOIN t_transporter ON t_transporter.trnsp_id = t_load_assigned.la_transporter_id
            LEFT JOIN t_map_load_src_dest_pair ON t_map_load_src_dest_pair.mlsdp_bidding_load_id = t_bidding_load.bl_id
            LEFT JOIN t_tracking_fleet ON t_tracking_fleet.tf_transporter_id = t_load_assigned.la_transporter_id
            WHERE
                t_bidding_load.is_active = true
                AND t_bidding_load.load_status = :load_status;"""


filter_wise_fetch_query="""
            SELECT
                t_bidding_load.bl_id,
                t_bidding_load.bid_time,
                t_bidding_load.reporting_from_time,
                t_bidding_load.reporting_to_time,
                t_bidding_load.bid_mode,
                t_bidding_load.bl_cancellation_reason,
                t_map_load_src_dest_pair.src_city,
                t_map_load_src_dest_pair.dest_city,
                t_load_assigned.la_transporter_id,
                t_load_assigned.trans_pos_in_bid,
                t_load_assigned.price,
                t_load_assigned.price_difference_percent,
                t_load_assigned.no_of_fleets_assigned,
                t_transporter.name,
                t_transporter.contact_no,
                t_tracking_fleet.tf_id,
                t_tracking_fleet.fleet_no,
                t_tracking_fleet.src_addrs,
                t_tracking_fleet.dest_addrs,
                t_load_assigned.is_active as la_active,
                t_transporter.is_active as tr_active,
                t_tracking_fleet.is_active as trf_active
            FROM t_bidding_load
            LEFT JOIN t_load_assigned ON t_load_assigned.la_bidding_load_id = t_bidding_load.bl_id
            LEFT JOIN t_transporter ON t_transporter.trnsp_id = t_load_assigned.la_transporter_id
            LEFT JOIN t_map_load_src_dest_pair ON t_map_load_src_dest_pair.mlsdp_bidding_load_id = t_bidding_load.bl_id
            LEFT JOIN t_tracking_fleet ON t_tracking_fleet.tf_transporter_id = t_load_assigned.la_transporter_id
            WHERE
                t_bidding_load.is_active = true
                AND t_bidding_load.load_status = :load_status
                $shipper_id_filter
                $regioncluster_id_filter
                $branch_id_filter
                $from_date_filter
                $to_date_filter
                ;"""


# load id
# multiple src and dest
# reporting date time
# bid date time
# variance approval
# load type
# transporter name
# approval status
# trackingId
# contact number 
# vehicle number
# cancellation reason

# ^^ Status wise loads
