from datetime import date
from djzbar.utils.informix import do_sql

class Individual:
    def __init__(self, id, year, acadYear):
        semester = 'RA'
        if date.today().month <= 5:
            semester = 'RC'

        #Query the information about the person
        personSQL = (
            ' SELECT'
            '   IDrec.id, TRIM(IDrec.firstname) AS firstname, TRIM(IDrec.lastname) AS lastname, TRIM(SRVrec.bldg) AS bldg'
            ' FROM'
            '   id_rec    IDrec    INNER JOIN    stu_serv_rec    SRVrec     ON  IDrec.id      =    SRVrec.id'
            '                                                               AND SRVrec.yr    =    %s'
            '                                                               AND SRVrec.sess =   "%s"'
            ' WHERE'
            '   IDrec.id  =   %s'
            ' GROUP BY id, firstname, lastname, bldg'
        ) % (year, semester, id)
        person = do_sql(personSQL).fetchone()

        #Load the record with placeholder data if the query returned no information
        if person == None:
            self.id = -1
            self.firstname = ''
            self.lastname = ''
            self.bldg = ''
        else:
            self.id = person.id
            self.firstname = person.firstname
            self.lastname = person.lastname
            self.bldg = person.bldg

        #Get the vehicle information for the specified user
        vehicleSQL = (
            ' SELECT'
            '   VEHrec.veh_no, VEHrec.id, VEHrec.model_yr, TRIM(INITCAP(VEHrec.make)) AS make, TRIM(INITCAP(VEHrec.model)) AS model, VEHrec.license, VEHrec.st_plate, NVL(PRKrec.permt_no,0) AS permitid,'
            '   PRKrec.lotcode, PRKrec.permit_code, TRIM(PRKrec.permtcmmnt) AS permitcomment, TO_CHAR(PRKrec.active_date, "%%m/%%d/%%Y") AS active_date,'
            '   TO_CHAR(PRKrec.inactive_date, "%%m/%%d/%%Y") AS inactive_date, TRIM(STKrec.permit_txt) AS permit_txt, VEHrec.acadyr AS acad_yr'
            ' FROM'
            '   veh_rec    VEHrec   LEFT JOIN    prkgpermt_rec    PRKrec    ON  VEHrec.veh_no       =    PRKrec.veh_no'
            '                       LEFT JOIN    prkgstckr_rec    STKrec    ON  PRKrec.permit_code  =    STKrec.permit_stckrcd'
            '                                                               AND VEHrec.acadyr       =    STKrec.permit_acadyr'
            ' WHERE'
            '   TODAY       BETWEEN VEHrec.issued_date AND NVL(VEHrec.inactive_date, TODAY)'
            '   AND'
            '   VEHrec.id       =   %s'
            '   AND'
            '   ('
            '       PRKrec.permt_no     IS  NULL'
            '       OR'
            '       TODAY           BETWEEN PRKrec.active_date  AND NVL(PRKrec.inactive_date, TODAY)'
            '   )'
            '   AND'
            '   VEHrec.acadyr    =    "%s"'
            ' ORDER BY PRKrec.permt_no'
        ) % (id, acadYear)

        vehicles = do_sql(vehicleSQL).fetchall()
        self.vehicle = []
        
        #Loop through the vehicle records and attach the information to the person's record.
        for vehicle in vehicles:
            stickers = Stickers().forLot(vehicle.lotcode, acadYear, vehicle.permit_txt)
            
            #Include the list of makes for the vehicle's year so that the dropdowns can be loaded properly.
            makes = Makes().getByYear(vehicle.model_yr)

            #Include the list of models for the vehicle's year so that the dropdowns can be loaded properly.
            models = Models().getByYearMake(vehicle.model_yr, vehicle.make)

            self.vehicle.append(Vehicle().load(vehicle, stickers, makes, models))
        
        self.vehicle.append(Vehicle())

class Vehicle:
    def __init__(self, veh_no = 0, id = 0, model_yr = "", make = "", model = "", license = "", st_plate = "", permitid = "", lotcode = "", permit_code = "", permitcomment = "", active_date = None, inactive_date = None, permit_txt = "", acad_yr = "", stickers = None, makes = None, models = None):
        self.veh_no = veh_no
        self.id = id
        self.model_yr = model_yr
        self.make = make
        self.model = model
        self.license = license
        self.st_plate = st_plate
        self.permitid = permitid
        self.lotcode = lotcode
        self.permit_code = permit_code
        self.permitcomment = permitcomment
        self.active_date = active_date
        self.inactive_date = inactive_date
        self.permit_txt = permit_txt
        self.acad_yr = acad_yr
        self.stickers = stickers
        self.makes = makes
        self.models = models

    def load(self, vehicle, stickers, makes, models):
        return Vehicle(
            vehicle.veh_no, vehicle.id, vehicle.model_yr, vehicle.make, vehicle.model, vehicle.license,
            vehicle.st_plate, vehicle.permitid, vehicle.lotcode, vehicle.permit_code, vehicle.permitcomment,
            vehicle.active_date, vehicle.inactive_date, vehicle.permit_txt, vehicle.acad_yr, stickers, makes, models
        )
    
    def loadByID(self, veh_no):
        vehicleSQL = (
            ' SELECT'
            '   VEHrec.veh_no, VEHrec.id, VEHrec.model_yr, TRIM(INITCAP(VEHrec.make)) AS make, TRIM(INITCAP(VEHrec.model)) AS model, VEHrec.license,'
            '   VEHrec.st_plate, PRKrec.permt_no AS permitid, PRKrec.lotcode, PRKrec.permit_code, TRIM(PRKrec.permtcmmnt) AS permitcomment,'
            '   TO_CHAR(PRKrec.active_date, "%%m/%%d/%%Y") AS active_date, TO_CHAR(PRKrec.inactive_date, "%%m/%%d/%%Y") AS inactive_date,'
            '   TRIM(STKrec.permit_txt) AS permit_txt, VEHrec.acadyr AS acad_yr'
            ' FROM'
            '    veh_rec    VEHrec  LEFT JOIN    prkgpermt_rec    PRKrec    ON  VEHrec.veh_no       =    PRKrec.veh_no'
            '                       LEFT JOIN    prkgstckr_rec    STKrec    ON  PRKrec.permit_code  =    STKrec.permit_stckrcd'
            '                                                               AND VEHrec.acadyr       =    STKrec.permit_acadyr'
            ' WHERE'
            '   VEHrec.veh_no   =   %s'
        ) % (veh_no)
        vehicle = do_sql(vehicleSQL).fetchone()

        makes = Makes().getByYear(vehicle.model_yr)
        models = Models().getByYearMake(vehicle.model_yr, vehicle.make)
        stickers = Stickers().forLot(vehicle.lotcode, vehicle.acad_yr, vehicle.permit_txt)
        return Vehicle(vehicle.veh_no, vehicle.id, vehicle.model_yr, vehicle.make, vehicle.model, vehicle.license, vehicle.st_plate, vehicle.permitid, vehicle.lotcode, vehicle.permit_code,
                       vehicle.permitcomment, vehicle.active_date, vehicle.inactive_date, vehicle.permit_txt, vehicle.acad_yr, makes, models, stickers)
    
    """
    def save(self, id, model_yr, make, model, license, st_plate, acad_yr, veh_no = 0):
        if veh_no == 0:
            insertVehicleSQL = (
                " INSERT INTO veh_rec (id, license, st_plate, make, model, model_yr, acadyr, issued_date)"
                " VALUES (%s, '%s', '%s', '%s', '%s', %s, '%s', TODAY)"
            ) % (id, license, st_plate, make, model, model_yr, acadyr)
            do_sql(insertVehicleSQL)
            getVehicleSQL = ("SELECT veh_no FROM veh_rec WHERE id = %s AND license = '%s' AND acadyr = '%s'") % (id, license, acadyr)
            veh_results = do_sql(getVehicleSQL).fetchone()
            veh_no = veh_results.veh_no
        else:
            updateVehicleSQL = (
                " UPDATE veh_rec"
                " SET license       =   '%s',"
                "   st_plate        =   '%s',"
                "   make            =   '%s',"
                "   model           =   '%s',"
                "   model_yr        =   %s"
                " WHERE"
                "   veh_no      =   %s"
            ) % (license, st_plate, make, model, model_yr, veh_no)
            do_sql(updateVehicleSQL)
        return veh_no
    """

class Sticker:
    def __init__(self, sticker_code, acad_year):
        getStickerSQL = (
            ' SELECT'
            '   ps.permit_stckrcd, ps.permit_txt, ps.permit_acadyr, ps.permit_assocdlot, ps.permt_stat, ps.issue_date, ps.inactive_date'
            ' FROM'
            '   prkgstckr_rec ps'
            ' WHERE'
            '   ps.permit_stckrcd = "%s"'
            ' AND'
            '   ps.permit_acadyr =   "%s"'
        ) % (sticker_code, acad_year)
        sticker = do_sql(getStickerSQL).fetchone();
        self.code = sticker.permit_stckrcd
        self.text = sticker.permit_txt
        self.acadyr = sticker.permit_acadyr
        self.lotcode = sticker.permit_assocdlot
        self.status = sticker.permt_stat
        self.issue_date = sticker.issue_date
        self.inactive_date = sticker.inactive_date

    def updateStatus(self, new_status):
        inactive_date = '"NULL"'
        if new_status != '' and new_status != 'A':
            inactive_date = "CURRENT"
        updateStickerSQL = (
            ' UPDATE'
            '    prkgstckr_rec'
            ' SET'
            '    permt_stat = "%s",'
            '    inactive_date = "%s"'
            ' WHERE'
            '    permit_stckrcd = "%s"'
            '    AND'
            '    permit_acadyr = "%s"'
        ) % (new_status, inactive_date, self.code, self.acadyr)
        do_sql(updateStickerSQL)

class Permit:
    def __init__(self, permit_no = 0):
        is_new = permit_no == 0
        if not is_new:
            selectPermitSQL = (
                ' SELECT'
                '    permt_no, lotcode, lotloctn, permit_code, acadyr, permt_id, veh_no, permt_stat, active_date, inactive_date, permtcmmnt'
                ' FROM'
                '    prkgpermt_rec'
                ' WHERE'
                '    permt_no = %s'
            ) % (permit_no)
            permit = do_sql(selectPermitSQL).fetchone()
        self.permit_no = 0 if is_new else permit.permt_no
        self.lotcode = "" if is_new else permit.lotcode
        self.lotloctn = "" if is_new else permit.lotloctn
        self.permit_code = "" if is_new else permit.permit_code
        self.acad_yr = "" if is_new else permit.acadyr
        self.student_id = 0 if is_new else permit.permt_id
        self.veh_no = 0 if is_new else permit.veh_no
        self.status = "" if is_new else permit.permt_stat
        self.active_date = None if is_new else permit.active_date
        self.inactive_date = None if is_new else permit.inactive_date
        self.comment = "" if is_new else permit.permtcmmnt

    def create(self, lotcode, lotloctn, permit_code, acadyr, student_id, veh_no, comment):
        insertPermitSQL = (
            ' INSERT INTO prkgpermt_rec (lotcode, lotloctn, permit_code, acad_yr, permt_id, veh_no, permt_stat, active_date, permtcmmnt)'
            ' VALUES ("%s", "%s", "%s", "%s", %s, %s, "A", CURRENT, "%s")'
        ) % (lotcode, lotloctn, permit_code, acadyr, student_id, veh_no, comment)
        do_sql(insertPermitSQL)
        
        getpermitidSQL = (
            ' SELECT permt_no'
            ' FROM prkgpermt_rec'
            ' WHERE veh_no = %s'
            ' AND inactive_date IS NULL'
        ) % (veh_no)
        permit = do_sql(getpermitidSQL).fetchone()
        self = Permit(permit.permt_no)

    def inactivate(self):
        #Step 1: Set inactive date for permit record
        inactivateSQL = (
            ' UPDATE'
            '    prkgpermt_rec'
            ' SET'
            '    inactive_date = CURRENT,'
            '    permt_stat = ""'
            ' WHERE'
            '    permt_no = %s'
        ) % (self.permit_no)
        do_sql(inactivateSQL)
        
        #Step 2: Open up spot in parking lot table
        freeUpSpotSQL = (
            ' UPDATE'
            '    prkglot_rec'
            ' SET'
            '    lot_stat = ""'
            ' WHERE'
            '    lotloctn = "%s"'
            '    AND'
            '    lot_acadyr = "%s"'
        ) % (self.lotloctn, self.acad_yr)
        do_sql(freeUpSpotSQL)

class Stickers:
    def __init__(self):
        self.permit_txt = ""
    
    def forLot(self, lot_code, acad_year, permit_txt = ''):
        stickerSQL = (
            ' SELECT TRIM(permit_txt) AS permit_txt'
            ' FROM prkgstckr_rec'
            ' WHERE LOWER(permit_assocdlot) = LOWER("%s")'
            ' AND (permt_stat = "" OR LOWER(permit_txt) = LOWER("%s"))'
            ' AND permit_acadyr = "%s"'
            ' ORDER BY permit_txt'
        ) % (lot_code, permit_txt, acad_year)
        return do_sql(stickerSQL).fetchall()

class Makes:
    def __init__(self):
        self.make_code = ""
        self.make_txt = ""

    def getByYear(self, valid_year, min_year = 1900):
        matchedMakesSQL = (
            ' SELECT'
            '   INITCAP(TRIM(make_code)) AS make_code'
            ' FROM'
            '   vehmodel_table'
            ' WHERE'
            '   startyr >       %s'
            '   AND'
            '   %s      BETWEEN startyr AND NVL(endyr, %s)'
            ' GROUP BY make_code'
            ' ORDER BY make_code'
        ) % (min_year, valid_year, valid_year)
        return do_sql(matchedMakesSQL).fetchall()

class Models:
    def __init__(self):
        self.model_code = ""
        self.model_txt = ""
        self.make = None
    
    def getByYearMake(self, model_year, make):
        matchedModelsSQL = (
            ' SELECT'
            '   INITCAP(TRIM(model_code)) AS model_code'
            ' FROM'
            '   vehmodel_table'
            ' WHERE'
            '   startyr >       %s'
            '   AND'
            '   %s      BETWEEN startyr AND NVL(endyr, %s)'
            '   AND'
            '   TRIM(LOWER(make_code))  =   "%s"'
            ' GROUP BY model_code'
            ' ORDER BY model_code'
        ) % (1900, model_year, model_year, make.lower())
        return do_sql(matchedModelsSQL).fetchall()  
