valid_load_status = ['draft', 'not_started', 'live', 'pending',
                     'partially_confirmed', 'confirmed', 'completed', 'cancelled']
valid_rebid_status = ['not_started', 'pending',
                      'partially_confirmed', 'confirmed']
valid_cancel_status = ['draft', 'not_started',
                       'pending', 'partially_confirmed', 'confirmed']
valid_assignment_status = ['pending', 'partially_confirmed']

valid_bid_status = ['live', 'not_started']

particpated_and_lost_status = ['pending','confirmed','partially_confirmed','completed']

valid_transporter_status = ['not_started','active', 'pending', 'assigned','live']


status_wise_fetch_query = """
            SELECT
                t_bidding_load.bl_id,
                t_bidding_load.bid_time,
                t_bidding_load.bid_end_time,
                t_bidding_load.bid_extended_time,
                t_bidding_load.reporting_from_time,
                t_bidding_load.reporting_to_time,
                t_bidding_load.bid_mode,
                t_bidding_load.bl_cancellation_reason,
                t_bidding_load.enable_tracking,
                t_bidding_load.no_of_fleets,
                t_bidding_load.fleet_type,
                t_bidding_load.completion_reason,
                (select name from t_lkp_fleet where t_lkp_fleet.id = t_bidding_load.fleet_type) as fleet_name,
                t_bidding_load.show_current_lowest_rate_transporter,
                t_bidding_load.bl_shipper_id,
				(select name from t_shipper where t_shipper.shpr_id = t_bidding_load.bl_shipper_id) as shipper_name,
                t_map_load_src_dest_pair.src_city,
                t_map_load_src_dest_pair.dest_city,
				(select array_agg(src_city) from t_map_load_src_dest_pair where t_map_load_src_dest_pair.mlsdp_bidding_load_id = t_bidding_load.bl_id and t_map_load_src_dest_pair.is_active=true) as src_cities,
				(select array_agg(dest_city) from t_map_load_src_dest_pair where t_map_load_src_dest_pair.mlsdp_bidding_load_id = t_bidding_load.bl_id and t_map_load_src_dest_pair.is_active=true) as dest_cities,
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
                t_tracking_fleet.is_active as trf_active,
                (select count(*) from t_bid_transaction where t_bid_transaction.bid_id = t_bidding_load.bl_id) as total_no_of_bids
            FROM t_bidding_load
            LEFT JOIN t_load_assigned ON t_load_assigned.la_bidding_load_id = t_bidding_load.bl_id
            LEFT JOIN t_transporter ON t_transporter.trnsp_id = t_load_assigned.la_transporter_id
            LEFT JOIN t_map_load_src_dest_pair ON (t_map_load_src_dest_pair.mlsdp_bidding_load_id = t_bidding_load.bl_id and t_map_load_src_dest_pair.is_active=true and t_map_load_src_dest_pair.is_prime=true)
            LEFT JOIN t_tracking_fleet ON (t_tracking_fleet.tf_transporter_id = t_load_assigned.la_transporter_id and t_tracking_fleet.tf_bidding_load_id = t_load_assigned.la_bidding_load_id and t_tracking_fleet.is_active = true)
            WHERE
                t_bidding_load.is_active = true
                AND t_bidding_load.load_status = :load_status
            ORDER BY
                t_bidding_load.created_at DESC
                """


filter_wise_fetch_query = """
            SELECT
                t_bidding_load.bl_id,
                t_bidding_load.bid_time,
                t_bidding_load.bid_end_time,
                t_bidding_load.bid_extended_time,
                t_bidding_load.reporting_from_time,
                t_bidding_load.reporting_to_time,
                t_bidding_load.bid_mode,
                t_bidding_load.bl_cancellation_reason,
                t_bidding_load.enable_tracking,
                t_bidding_load.no_of_fleets,
                t_bidding_load.fleet_type,
                t_bidding_load.completion_reason,
                (select name from t_lkp_fleet where t_lkp_fleet.id = t_bidding_load.fleet_type) as fleet_name,
                t_bidding_load.show_current_lowest_rate_transporter,
                t_bidding_load.bl_shipper_id,
				(select name from t_shipper where t_shipper.shpr_id = t_bidding_load.bl_shipper_id) as shipper_name,
                t_map_load_src_dest_pair.src_city,
                t_map_load_src_dest_pair.dest_city,
				(select array_agg(src_city) from t_map_load_src_dest_pair where t_map_load_src_dest_pair.mlsdp_bidding_load_id = t_bidding_load.bl_id and t_map_load_src_dest_pair.is_active=true) as src_cities,
				(select array_agg(dest_city) from t_map_load_src_dest_pair where t_map_load_src_dest_pair.mlsdp_bidding_load_id = t_bidding_load.bl_id and t_map_load_src_dest_pair.is_active=true) as dest_cities,
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
                t_tracking_fleet.is_active as trf_active,
                (select count(*) from t_bid_transaction where t_bid_transaction.bid_id = t_bidding_load.bl_id) as total_no_of_bids
            FROM t_bidding_load
            LEFT JOIN t_load_assigned ON t_load_assigned.la_bidding_load_id = t_bidding_load.bl_id
            LEFT JOIN t_transporter ON t_transporter.trnsp_id = t_load_assigned.la_transporter_id
            LEFT JOIN t_map_load_src_dest_pair ON (t_map_load_src_dest_pair.mlsdp_bidding_load_id = t_bidding_load.bl_id and t_map_load_src_dest_pair.is_active=true and t_map_load_src_dest_pair.is_prime = true)
            LEFT JOIN t_tracking_fleet ON (t_tracking_fleet.tf_transporter_id = t_load_assigned.la_transporter_id and t_tracking_fleet.tf_bidding_load_id = t_load_assigned.la_bidding_load_id and t_tracking_fleet.is_active = true)
            WHERE
                t_bidding_load.is_active = true
                AND t_bidding_load.load_status = :load_status
                $shipper_id_filter
                $regioncluster_id_filter
                $branch_id_filter
                $from_date_filter
                $to_date_filter
            ORDER BY
                t_bidding_load.created_at DESC
                ;"""


live_bid_details = '''
SELECT
    t_transporter.name AS transporter_name,
    t_bid_transaction.transporter_id,
    t_bid_transaction.created_at,
    MIN(t_bid_transaction.rate) AS rate,
    t_bid_transaction.comment AS comment,
    MAX(t_bid_transaction.attempt_number) AS attempts
FROM
    t_bid_transaction
JOIN
    t_transporter ON t_bid_transaction.transporter_id = t_transporter.trnsp_id
where 
	t_bid_transaction.bid_id = :bid_id
GROUP BY
    t_transporter.name,
    t_bid_transaction.transporter_id,
    t_bid_transaction.comment,
    t_bid_transaction.created_at;
'''

lost_participated_transporter_bids = '''
SELECT DISTINCT bt.bid_id
FROM t_bid_transaction bt
LEFT JOIN t_load_assigned la
ON bt.bid_id = la.la_bidding_load_id AND bt.transporter_id = la.la_transporter_id
WHERE bt.transporter_id = :transporter_id  AND (la.la_id IS NULL OR (la.is_active = true AND (la.is_assigned = false OR la.is_assigned is NULL )))
'''

transporter_analysis = '''SELECT
    tt."name" AS transporter_name,
    COUNT(DISTINCT tbl.bl_id) AS participated_bids,
    COUNT(DISTINCT tla.la_bidding_load_id) AS selected_bids,
    AVG(EXTRACT(DAY FROM (tla.created_at - tbl.bid_end_time))) AS avg_assignment_delay_days
FROM
    t_transporter tt
LEFT JOIN
    t_bid_transaction tbt ON tt.trnsp_id = tbt.transporter_id
LEFT JOIN
    t_bidding_load tbl ON tbl.bl_id = tbt.bid_id AND tbl.is_active = true
LEFT JOIN
    t_load_assigned tla ON tla.la_bidding_load_id = tbl.bl_id AND tla.is_active = true AND tla.la_transporter_id = tt.trnsp_id
'''


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
