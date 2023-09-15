from sqlalchemy import BigInteger, Boolean, Column, DateTime, Enum, ForeignKey, String, text, Double, JSON, Integer
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID

from config.db_config import Base

class Persistance:
    created_at = Column(DateTime, nullable = False, server_default = text("now()"))
    created_by = Column(UUID(as_uuid=True), ForeignKey('t_user.user_id'), nullable = False)
    updated_at = Column(DateTime, nullable = True)
    updated_by = Column(UUID(as_uuid=True), ForeignKey('t_user.user_id'), nullable = True)
    is_active = Column(Boolean, nullable=False, default=True)

class Shipper(Base, Persistance):
    __tablename__ = "t_shipper"

    shpr_id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    name = Column(String, nullable=False)
    email = Column(String, nullable = False)
    contact_person = Column(String, nullable=False)
    contact_no = Column(String, nullable=False)
    corporate_address = Column(String, nullable=False)
    corporate_city = Column(String, nullable=False)
    corporate_state = Column(String, nullable=False)
    corporate_country = Column(String, nullable= False)
    corporate_postal_code= Column(String, nullable=True)
    billing_address = Column(String, nullable = False)
    billing_city = Column(String, nullable=False)
    billing_state = Column(String, nullable=False)
    billing_country = Column(String, nullable= False)
    billing_postal_code= Column(String, nullable=True)
    logo = Column(String, nullable=True)
    pan = Column(String, nullable = False)
    tan = Column(String, nullable = False)
    gstin = Column(String, nullable = True)
    inc_cert = Column(String, nullable = True)
    cin = Column(String, nullable = True)
    trade_license = Column(String, nullable = True)
    doc_path= Column(String, nullable=True)
    has_region = Column(Boolean, default = False, nullable = False)
    has_cluster = Column(Boolean, default = False, nullable = False)
    has_branch = Column(Boolean, default = False, nullable = False)
    registration_step = Column(Integer, nullable=False, default=0)
    colour_scheme = Column(JSON, nullable = True)
    status = Column(Enum('verified', 'approved', 'pending', 'rejected', 'blocked' , name = 'approval_status'), default = 'pending')
    license = relationship("MapShipperLicense", uselist=False)
    #some issue in enum naming consistency

class MapShipperRegionCluster(Base, Persistance):
    __tablename__ = "t_map_shipper_region_cluster" 

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"), nullable=False)
    shipper_id = Column(UUID(as_uuid=True), ForeignKey('t_shipper.shpr_id'), nullable=True)
    region_cluster_id = Column(UUID(as_uuid=True), ForeignKey('t_lkp_region_cluster.id'), nullable=True)
    
    
class Branch(Base, Persistance):
    __tablename__ = "t_branch"

    branch_id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"), nullable=True)
    name = Column(String, nullable=True)
    branch_shipper_id = Column(UUID(as_uuid=True), ForeignKey('t_shipper.shpr_id'), nullable=True)
    branch_region_cluster_id = Column(UUID(as_uuid=True), ForeignKey('t_lkp_region_cluster.id'), nullable=True)
    gstin = Column(String, nullable=True)
    contact_person = Column(String, nullable=True)
    contact_no = Column(String, nullable=True)
    email = Column(String, nullable=True)
    address = Column(String, nullable=True)
    city = Column(String, nullable=True)
    state = Column(String, nullable=True)
    country = Column(String, nullable= True)
    postal_code = Column(String, nullable=True)
    doc_path = Column(String, nullable=True)


class Segment(Base, Persistance):
    __tablename__ = "t_segment"

    seg_id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"), nullable=False)
    name = Column(String, nullable = False) 
    seg_shipper_id = Column(UUID(as_uuid = True), ForeignKey("t_shipper.shpr_id"), nullable = True) 


class Comment(Base, Persistance):
    __tablename__ = "t_comment"

    cmmnt_id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"), nullable=False)
    cmmnt_text = Column(String, nullable=False)
    cmmnt_shipper_id = Column(UUID(as_uuid=True), ForeignKey("t_shipper.shpr_id"), nullable=False)


class MapTransporterSegment(Base, Persistance):
    __tablename__ = "t_map_transporter_segment"

    mts_id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"), nullable=False)
    mts_transporter_id = Column(UUID(as_uuid=True), ForeignKey("t_transporter.trnsp_id"), nullable=True)
    mts_segment_id = Column(UUID(as_uuid=True), ForeignKey("t_segment.seg_id"), nullable=True)
    
class BlacklistTransporter(Base, Persistance):
    __tablename__ = "t_blacklist_transporter"

    bt_id = Column(UUID(as_uuid = True), primary_key = True, server_default = text("gen_random_uuid()"), nullable = False)
    bt_transporter_id = Column(UUID(as_uuid = True), ForeignKey("t_transporter.trnsp_id"), nullable = False)
    bt_shipper_id = Column(UUID(as_uuid = True), ForeignKey("t_shipper.shpr_id"), nullable = True)
    bt_bidding_load_id = Column(UUID(as_uuid = True), ForeignKey("t_bidding_load.bl_id"), nullable = True)
    reason = Column(String, nullable = True)


class WorkflowApprovals(Base, Persistance):
    __tablename__ = "t_workflow_approvals"
    
    wa_id = Column(UUID(as_uuid = True), primary_key = True, server_default = text("gen_random_uuid()"), nullable = False)
    wa_user_id = Column(UUID(as_uuid = True), ForeignKey("t_user.user_id"), nullable = False)
    wa_manager_id = Column(UUID(as_uuid = True), ForeignKey("t_user.user_id"), nullable = False)
    wa_load_id = Column(UUID(as_uuid = True), ForeignKey("t_bidding_load.bl_id"), nullable = True)
    approval_status = Column(Enum('verified', 'approved', 'pending', 'rejected', 'blocked' , name = 'approval_status'), default = 'pending')




##########  Shipper Settings   ###############

class AppSettings(Base, Persistance):
    __tablename__ = "t_app_settings"

    appsett_id = Column(  UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()") ,nullable= False)
    settings_key = Column( String ,nullable= False)
    settings_value = Column( String ,nullable= False) 


class Settings(Base, Persistance):
    __tablename__ = "t_settings"

    sttng_id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"), nullable=False)
    sttng_shipper_id = Column(UUID(as_uuid=True), ForeignKey("t_shipper.shpr_id"), nullable=True) 
    sttng_branch_id = Column(UUID(as_uuid=True), ForeignKey("t_branch.branch_id"), nullable=True) 
    communicated_by = Column( Enum("sms", "email", "whatsapp","sms_email","sms_whatsapp","email_whatsapp","all", name = 'communication_medium'), default = 'whatsapp',nullable=False)
    returning_fleet_radius = Column(Integer, nullable = True)
    tracking_ping = Column(Integer, nullable=False, default=15)
    epod_type = Column(Enum("load_wise", "item_wise", "invoice_wise", "none", name="type_of_epod"), default=None)
    eta = Column(Boolean, nullable=True, default=False)

class BidSettings(Base, Persistance):
    __tablename__ =  "t_bid_settings"
    
    bdsttng_id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"), nullable=False)
    bdsttng_shipper_id = Column(UUID(as_uuid=True), ForeignKey("t_shipper.shpr_id") ,nullable= False)
    bdsttng_branch_id = Column( UUID(as_uuid=True), ForeignKey("t_branch.branch_id") ,nullable= True)
    bid_mode = Column( Enum('private_pool', 'open_market' , name = 'bid_mode_type') ,nullable= False)
    bid_duration = Column( Integer,nullable= False)
    bid_increment_time = Column( Integer ,nullable= False)
    bid_increment_duration = Column( Integer ,nullable= False)
    bid_price_decrement = Column(Double ,nullable= False)
    show_current_lowest_rate_transporter = Column( Boolean ,nullable= False)
    show_bid_info_during_bid = Column( Boolean ,nullable= False)
    enable_bid_match = Column( Boolean ,nullable= False)
    bid_match_duration = Column( Integer ,nullable= False)
    allow_public_mode = Column( Boolean ,nullable= False)
    bdsttng_rate_quote_type = Column( UUID(as_uuid=True), ForeignKey("t_lkp_uom.id") ,nullable= False)
    

class BidInfoDisplaySettings ( Base, Persistance):
    __tablename__ = "t_bid_info_display_settings"
    
    id = Column( UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()") , nullable= False)
    bds_shipper_id = Column( UUID(as_uuid=True), ForeignKey("t_shipper.shpr_id") , nullable= False)
    show_bid_transporter_name = Column( Boolean, default=False , nullable= False)
    show_bid_transporter_rate = Column( Boolean, default=False , nullable= False)
    bds_role_id = Column( UUID(as_uuid=True), ForeignKey("t_lkp_role.id")  , nullable= False)
    apply_to_all_roles = Column( Boolean, default=False , nullable= False)


class geofenceSettings(Base, Persistance):
    __tablename__ = "t_geofence_settings"
    
    gfnc_sttng_id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"), nullable=False)
    gfnc_sttng_shipper_id = Column( UUID(as_uuid=True), ForeignKey("t_shipper.shpr_id"), nullable=False)
    gfnc_sttng_branch_id = Column(UUID(as_uuid=True), ForeignKey("t_branch.branch_id"),nullable=True)
    source_radius = Column(Integer ,nullable=False)
    arrival_radius = Column(Integer ,nullable=False)
    trip_close_radius = Column(Integer ,nullable=False)
    trip_close_method = Column(Enum('pod', 'radius', name = 'trip_closure_method'), default = 'radius')


class alertSettings(Base, Persistance):
    __tablename__ = "t_alert_settings"
    
    alrt_sttng_id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"), nullable=False)
    alrt_sttng_shipper_id = Column(UUID(as_uuid=True), ForeignKey("t_shipper.shpr_id"), nullable=False)
    alrt_sttng_branch_id = Column(UUID(as_uuid=True), ForeignKey("t_branch.branch_id"), nullable=True)
    vehicle_hold_long = Column(Integer ,nullable=False)
    verhicle_hold_short = Column(Integer ,nullable=False)
    departure_long = Column(Integer ,nullable=False)
    departure_short = Column(Integer ,nullable=False)
    delay_long = Column(Integer ,nullable=False)
    delay_short = Column(Integer ,nullable=False)
    arrival_long = Column(Integer ,nullable=False)
    arrival_short = Column(Integer ,nullable=False)
    route_deviate = Column(Boolean ,nullable=False, default=True)
    sos_enabled = Column(Boolean ,nullable=False, default=True)


##########  Mappings   ###############
class MapShipperModule(Base, Persistance):
    __tablename__ = "t_map_shipper_module"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"), nullable=False)
    shipper_id = Column(UUID(as_uuid=True), ForeignKey("t_shipper.shpr_id"), nullable=False)
    module_id = Column(UUID(as_uuid=True), ForeignKey("t_lkp_module.id"), nullable=False)


class MapShipperroleSubmodule(Base, Persistance):
    __tablename__ = "t_map_shipper_role_submodule"
    
    msrs_id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"), nullable=False)
    msrs_shipper_id = Column(UUID(as_uuid=True), ForeignKey('t_shipper.shpr_id'), nullable=True)
    msrs_branch_id = Column(UUID(as_uuid=True), ForeignKey('t_branch.branch_id'), nullable=True)
    msrs_role_id = Column(UUID(as_uuid=True), ForeignKey('t_lkp_role.id'), nullable=True)
    msrs_submodule_id = Column(UUID(as_uuid=True), ForeignKey('t_lkp_submodule.id'), nullable=False)
    role = relationship("LkpRole")
    submodule = relationship("LkpSubModule")
    

class MapShipperCurrency(Base, Persistance):
    __tablename__ = "t_map_shipper_currency"
    
    msc_id = Column(UUID(as_uuid= True),  primary_key=True, server_default=text("gen_random_uuid()"), nullable=False)
    msc_shipper_id = Column(UUID(as_uuid= True), ForeignKey("t_shipper.shpr_id") , nullable=False)
    msc_currency_id = Column(UUID(as_uuid= True), ForeignKey("t_lkp_currency.id"), nullable=False)
    
class MapShipperLicense(Base, Persistance):
    __tablename__ = "t_map_shipper_license"
    
    msl_id = Column(UUID(as_uuid = True),  primary_key = True, server_default = text("gen_random_uuid()"), nullable = False)
    msl_shipper_id = Column(UUID(as_uuid = True), ForeignKey("t_shipper.shpr_id") ,nullable = False)
    msl_licence_id = Column(UUID(as_uuid = True), ForeignKey("t_lkp_license.id") ,nullable = False)
    msl_price = Column(Double, nullable = False)
    expiry_date = Column(DateTime, nullable=True)


##########  User   ###############
class User(Base, Persistance):
    __tablename__= "t_user"
    
    user_id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"), nullable=False)  
    user_shipper_id = Column(UUID(as_uuid=True), ForeignKey('t_shipper.shpr_id'), nullable=True)
    user_transporter_id = Column(UUID(as_uuid=True), ForeignKey('t_transporter.trnsp_id'), nullable=True)
    name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    contact_no = Column(String, nullable=False)
    otp = Column(String, nullable=True)
    is_sos_user = Column(Boolean, default=False)
    user_type = Column(Enum('shp', 'trns', 'acu', name = 'user_type'), default = 'shp')
    workflow_threshold_value = Column(Double, nullable=True)
    user_manager_id = Column(UUID(as_uuid=True), ForeignKey('t_user.user_id'), nullable=True)

class MapUser(Base, Persistance):
    __tablename__ = "t_map_user"

    mpus_id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"), nullable=False)
    mpus_user_id = Column(UUID(as_uuid=True), ForeignKey("t_user.user_id"), nullable=False)
    mpus_shipper_id = Column(UUID(as_uuid=True), ForeignKey("t_shipper.shpr_id"), nullable=False)
    mpus_region_cluster_id  = Column(UUID(as_uuid=True), ForeignKey("t_lkp_region_cluster.id"), nullable=True)
    mpus_branch_id = Column(UUID(as_uuid=True), ForeignKey("t_branch.branch_id"), nullable=True)
    mpus_role_id = Column(UUID(as_uuid=True), ForeignKey("t_lkp_role.id"), nullable=False)


##########  Load & Bid   ###############

class BiddingLoad(Base, Persistance):
    __tablename__ = "t_bidding_load"

    bl_id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"), nullable=False)
    bl_shipper_id = Column(UUID(as_uuid=True), ForeignKey("t_shipper.shpr_id"), nullable=False)
    bl_region_cluster_id = Column(UUID(as_uuid=True), ForeignKey('t_lkp_region_cluster.id'))
    bl_branch_id = Column(UUID(as_uuid=True), ForeignKey("t_branch.branch_id"))
    load_type = Column(Enum('reverse', 'forward' , name = 'load_type'), default = 'reverse',nullable=False)
    bid_type = Column(Enum('spot', 'contractual' , name = 'bid_type'), default = 'spot',nullable=False)
    bid_mode = Column(Enum('private_pool', 'open_market' , name = 'bid_mode_type'), default = 'private_pool',nullable=False)
    show_current_lowest_rate_transporter = Column(Boolean, default=False)
    bid_price_decrement = Column(Double, default=1,nullable=False)
    no_of_tries = Column(Integer, default=9999)
    loading_contact_name = Column(String, nullable = False)
    loading_contact_no = Column(String, nullable = False)
    unloading_contact_name = Column(String, nullable = False)
    unloading_contact_no = Column(String, nullable = False)
    bid_time = Column(DateTime, nullable = False)
    net_qty = Column(Double, default=1,nullable=False)
    fleet_type = Column(UUID(as_uuid=True), ForeignKey("t_lkp_fleet.id"))
    no_of_fleets = Column(Integer, default=1)
    reporting_from_time = Column(DateTime, nullable = False)
    reporting_to_time = Column(DateTime, nullable = False)
    comments = Column(String, nullable = True) 
    requirements_from_transporter = Column(String, nullable = True) 
    load_status = Column(Enum('draft','not_started','live','pending','partially_confirmed','confirmed', 'completed','cancelled' , name = 'load_status_type'), default = 'not_started')
    epod_type = Column(Enum('load_wise', 'item_wise', 'invoice_wise', 'none' , name = 'epod_type'), default = 'none')
    reassign = Column(Integer, default=0)
    rebid = Column(Boolean, default=False)
    split = Column(Boolean, default=False)
    enable_tracking = Column(Boolean, default=False)
    base_price = Column(Double, default=0.0,nullable=False)
    system_base_price = Column(Double, default=0.0,nullable=False)
    is_cancelled  = Column(Boolean, default=False)
    bl_cancellation_reason = Column(UUID(as_uuid=True), ForeignKey("t_lkp_reason.id")) 
    is_published = Column(Boolean, default=False)


class LoadAssigned(Base, Persistance):
    __tablename__= "t_load_assigned"
    
    la_id = Column(UUID(as_uuid= True),  primary_key = True, server_default = text("gen_random_uuid()"), nullable = False)
    la_bidding_load_id = Column(UUID(as_uuid = True), ForeignKey("t_bidding_load.bl_id") ,nullable = False)
    la_transporter_id = Column(UUID(as_uuid = True), ForeignKey("t_transporter.trnsp_id") ,nullable = False)
    trans_pos_in_bid = Column(String, nullable = False)
    price = Column(Double, nullable = True)
    price_difference_percent = Column(Double, nullable = True)
    no_of_fleets_assigned = Column(Integer, nullable = True)


class Notification(Base, Persistance):
    __tablename__ = "t_notification"

    nt_id = Column(UUID(as_uuid = True), primary_key = True, server_default = text("gen_random_uuid()"), nullable = False)    
    nt_receiver_id = Column(UUID(as_uuid = True), ForeignKey("t_user.user_id"), nullable = False)
    nt_sender_id = Column(UUID(as_uuid = True), ForeignKey("t_user.user_id"), nullable = True)
    nt_text = Column(String, nullable = False)
    nt_type = Column(String, nullable = False)
    is_read = Column(String, nullable = False, default = False)
    

class BidParticipation (Base, Persistance):
    __tablename__ = "t_bid_participation"
    
    bp_id= Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()") , nullable= False)
    bp_bidding_load_id= Column(UUID(as_uuid=True), ForeignKey("t_bidding_load.bl_id") ,nullable=False)
    bp_transporter_id= Column(UUID(as_uuid=True),ForeignKey("t_transporter.trnsp_id") ,nullable=False)
    try_sequence= Column(Integer,nullable=True)
    is_price_match_entry= Column(Boolean,nullable=False, default=False)
    price= Column(Double,nullable=False)
    comments= Column(String,nullable=True)


class PriceMatchRequest(Base, Persistance):
    __tablename__ = "t_price_match_request"
    
    pmr_id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()") , nullable= False)
    pmr_bidding_load_id = Column(UUID(as_uuid=True), ForeignKey("t_bidding_load.bl_id") ,nullable=True)
    pmr_shipper_id = Column(UUID(as_uuid=True), ForeignKey("t_shipper.shpr_id"), nullable=True)
    pmr_transporter_id = Column(UUID(as_uuid=True),ForeignKey("t_transporter.trnsp_id") ,nullable=True)
    pmr_price = Column(Double,nullable=False)
    is_approved = Column(Boolean,nullable=False, default=False)



class MapLoadMaterial(Base, Persistance):
    __tablename__ = "t_map_load_material"
    
    mlm_id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"), nullable=False)
    mlm_bidding_load_id = Column(UUID(as_uuid=True), ForeignKey("t_bidding_load.bl_id"), nullable=False)
    mlm_material_id = Column(UUID(as_uuid=True), ForeignKey("t_lkp_material.id"), nullable=False)
    qty = Column(Double, nullable=False)




class MapLoadEpodItemWise(Base, Persistance):
    __tablename__ ="t_map_load_epod_itemwise"
    
    mlei_id = Column(UUID(as_uuid= True),  primary_key=True, server_default=text("gen_random_uuid()"), nullable=False)
    mlei_bidding_load_id = Column(UUID(as_uuid= True), ForeignKey("t_bidding_load.bl_id"), nullable=True)
    mlei_src_dest_id = Column(UUID(as_uuid= True), ForeignKey("t_map_load_src_dest_pair.mlsdp_id"), nullable=True)
    item_name = Column(String, nullable=False)
    items_count_weight = Column(Double,nullable=True)
    actual_count_weight = Column(Double,nullable=True)
    count_unit = Column(String,nullable=True)
    status = Column(Enum("recieved", "pending", name = 'epod_status'), default = 'pending', nullable= False)


class MapLoadEpodInvoiceWise(Base, Persistance):
    __tablename__ = "t_map_load_epod_invoicewise"

    mlein_id = Column(UUID(as_uuid= True),  primary_key=True, server_default=text("gen_random_uuid()"), nullable=False)
    mlein_bidding_load_id = Column(UUID(as_uuid= True), ForeignKey("t_bidding_load.bl_id"), nullable = True)
    mlein_src_dest_id = Column(UUID(as_uuid= True), ForeignKey("t_map_load_src_dest_pair.mlsdp_id"), nullable=True)
    mlein_epod_link = Column(String, nullable=True)



###################### tracking ############################


class Tracking( Base, Persistance):
    __tablename__="t_tracking"
    
    trck_id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"), nullable=False)
    trck_bidding_load_id = Column(UUID(as_uuid=True), ForeignKey("t_bidding_load.bl_id"),nullable=True)
    trck_fleet_id = Column(UUID(as_uuid=True), ForeignKey("t_tracking_fleet.tf_id"),nullable=True)
    lat = Column(Double,nullable=False)
    long = Column(Double,nullable=False)
    estimated_time = Column(DateTime,nullable=True)
    actual_time = Column(DateTime,nullable=True)
    is_source = Column(Boolean,nullable=True)
    alert_type = Column( Enum("departure", "arrival","vehicle_hold","deviation","sos","none", name = 'alert_types'), default = 'None',nullable=True)
    alert_duration = Column(String,nullable=True)


class TrackingFleet(Base, Persistance):
    __tablename__="t_tracking_fleet"
    
    tf_id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"), nullable=False)
    tf_bid_load_id = Column(UUID(as_uuid=True), ForeignKey("t_bidding_load.bl_id"),nullable= True)
    tf_transporter_id = Column(UUID(as_uuid=True), ForeignKey("t_transporter.trnsp_id"),nullable= True)
    tf_fleet_type_id = Column(UUID(as_uuid=True), ForeignKey("t_lkp_fleet.id"),nullable= True)
    src_addrs = Column( String,nullable= False)
    src_lat = Column( String,nullable= False)
    src_long = Column( String,nullable= False)
    dest_addrs = Column( String,nullable= True)
    dest_lat = Column( String,nullable= True)
    dest_long = Column( String,nullable= True)
    inter_addrs = Column( String,nullable= False)
    inter_lat = Column( String,nullable= False)
    inter_long = Column( String,nullable= False)
    fleet_no = Column( String,nullable= False)
    driver_name = Column( String,nullable= False)
    driver_number = Column( String,nullable= False)
    tf_netw_srvc_prvd_id = Column(UUID(as_uuid=True), ForeignKey("t_lkp_network_provider.id"),nullable= True)
    alternate_driver_name = Column(String,nullable= False)
    alternate_driver_number = Column(String,nullable= False)
    tf_altr_netw_srvc_prvd_id = Column(UUID(as_uuid=True), ForeignKey("t_lkp_network_provider.id"),nullable= True)
    gate_in = Column(DateTime,nullable= False)
    vehicle_doc = Column(DateTime,nullable= False)
    vehicle_doc_link = Column(String,nullable= False)
    loading_start = Column(DateTime,nullable= False)
    loading_end = Column(DateTime,nullable= False)
    company_doc_link = Column(String,nullable= False)
    gate_out = Column(DateTime,nullable= False)
    eway = Column(String,nullable= True)
    eway_expire = Column(DateTime,nullable= True)
    consent = Column( Boolean,default= False,nullable= False)
    is_draft = Column( Boolean,default= True, nullable=False)
    
    
    
##Transporter
    

class TransporterModel(Base,Persistance):
    __tablename__ = "t_transporter"
    
    trnsp_id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"), nullable=False)
    name = Column(String,nullable=False)
    logo = Column(String,nullable=True)
    corporate_address = Column(String,nullable=False)
    corporate_city = Column(String,nullable=False)
    corporate_state = Column(String,nullable=False)
    corporate_postal_code = Column(String,nullable=False)
    corporate_country = Column(String,nullable=False)
    billing_address = Column(String,nullable=False)
    billing_city = Column(String,nullable=False)
    billing_state = Column(String,nullable=False)
    billing_postal_code = Column(String,nullable=False)
    billing_country = Column(String,nullable=False)
    contact_name = Column(String,nullable=False)
    contact_no = Column(String,nullable=False)
    email = Column(String,nullable=False)
    communicate_by = Column( Enum("sms", "email", "whatsapp","sms_email","sms_whatsapp","email_whatsapp","all", name = 'communication_medium'), default = 'whatsapp',nullable=False)
    pan = Column(String,nullable=False)
    tan = Column(String,nullable=True)
    gstin = Column(String,nullable=False)
    no_of_vehicles = Column(Integer,nullable=True)
    leased_vehicles = Column(Integer,nullable=True)
    carriage_act_cert = Column(String,nullable=True)
    iba_approved = Column(Boolean,default=False, nullable=True)
    iba_cert = Column(String,nullable=True)



class MapTransporterFleet(Base, Persistance):
    __tablename__ = "t_map_transporter_fleet"
    
    mtf_id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    mtf_transporter_id = Column(UUID(as_uuid=True), ForeignKey("t_transporter.trnsp_id"),nullable= True)
    mtf_fleet_id = Column(UUID(as_uuid=True), ForeignKey("t_lkp_fleet.id"),nullable= True)
    qty = Column(Double, nullable=False)
    ownership_status = Column( Enum("owned", "leased", name = 'ownership_status'), default = 'owned',nullable=False)


###########     Master Tables   #############

class LkpCountry(Base, Persistance):
    __tablename__ = "t_lkp_country"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    name = Column(String, nullable=False)
    
    
class LkpNetworkProvider(Base, Persistance):
    __tablename__ = "t_lkp_network_provider"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    name = Column(String, nullable=False)
    
    
class LkpUom(Base, Persistance):
    __tablename__ = "t_lkp_uom"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    type = Column(String, nullable=False)
    
    
class LkpReason(Base, Persistance):
    __tablename__ = "t_lkp_reason"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    type = Column(String, nullable=False)
    desc = Column(String, nullable=False)
    
class LkpMaterial(Base, Persistance):
    __tablename__ = "t_lkp_material"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    type = Column(String, nullable=False)
    name = Column(String, nullable=False)
    
    
class LkpFleet(Base, Persistance):
    __tablename__ = "t_lkp_fleet"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    type = Column(String, nullable=False)
    name = Column(String, nullable=False)
    wheels = Column(BigInteger, nullable=False)
    capacity = Column(BigInteger, nullable=False)
    std_travel_dist_per_day = Column(BigInteger, nullable=False)

class LkpRole(Base, Persistance):
    __tablename__ = "t_lkp_role"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"), nullable=False)  
    role_name = Column(String, nullable=False)
    shipper_id = Column(UUID(as_uuid=True), ForeignKey('t_shipper.shpr_id'), nullable=True)      #can be blank


class LkpModule(Base, Persistance):
    __tablename__ = "t_lkp_module"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"), nullable=False)
    name = Column(String, nullable=False)
    type = Column(Enum("auth", "load", "bid", "track", "settings", "analytics", name = 'module_type'), default = 'load')
    submodules = relationship("LkpSubModule")

class LkpSubModule(Base, Persistance):
    __tablename__ = "t_lkp_submodule"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"), nullable=False)
    module_id = Column(UUID(as_uuid=True), ForeignKey("t_lkp_module.id"), nullable=False)
    submodule_name = Column(String, nullable=True)

class LkpLicense(Base, Persistance):
    __tablename__ = "t_lkp_license"
   
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"), nullable=False)
    name = Column(String, nullable=False)
    type = Column(Enum("user_basis", "usage_basis", name="license_type"), default="user_basis")
    details = Column(String, nullable=False)
    price = Column(Double, nullable=False)
    
class LkpRegionCluster(Base, Persistance):
    __tablename__ = "t_lkp_region_cluster"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"), nullable=False)
    name = Column(String, nullable = False)
    details = Column(String, nullable = True)
    is_region = Column(Boolean, nullable = False, default = False)

class LkpCurrency(Base, Persistance):
    __tablename__ = "t_lkp_currency"
   
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"), nullable=False)
    name = Column(String, nullable=False)
    country = Column(String, nullable=False)


class BidTransaction(Base,Persistance):
    __tablename__ = 't_bid_transaction'
    
    id = Column (UUID(as_uuid=True), primary_key=True,server_default=text('gen_random_uuid()'),nullable=False)
    bid_id = Column(UUID(as_uuid=True),ForeignKey('t_bidding_load.bl_id'),nullable=False)
    transporter_id = Column(UUID(as_uuid=True),ForeignKey('t_transporter.trnsp_id'),nullable=False)
    rate = Column(Double,nullable=False)
    comment = Column(String,nullable=False)
    attempt_number = Column(Integer,nullable=False)


class MapLoadSrcDestPair(Base, Persistance):
    __tablename__ = "t_map_load_src_dest_pair"
    
    mlsdp_id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"), nullable=False)
    mlsdp_bidding_load_id = Column(UUID(as_uuid=True), ForeignKey("t_bidding_load.bl_id"), nullable = True)
    src_street_address = Column(String, nullable= False)
    src_city = Column(String, nullable= False)
    src_state = Column(String, nullable= False)
    src_postal_code = Column( String, nullable= False)
    src_country = Column( String, nullable= False)
    src_lat = Column(Double, nullable= True)
    src_long = Column(Double, nullable= True)
    dest_street_address = Column( String, nullable= False)
    dest_city = Column( String, nullable= False)
    dest_state = Column( String, nullable= False)
    dest_postal_code = Column( String, nullable= False)
    dest_country = Column( String, nullable= False)
    dest_lat = Column(Double, nullable= True)
    dest_long = Column(Double, nullable= True)
    contact_name = Column(String, nullable= True)
    contact_no = Column(String, nullable= True)
    is_item_wise_epod = Column(Boolean, nullable= False)
    epod_status = Column( Enum("recieved", "pending", name = 'epod_status'), default = 'pending', nullable= True)