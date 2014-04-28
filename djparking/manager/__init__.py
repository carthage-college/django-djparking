from djzbar.utils.informix import do_sql
#from djparking.manager.views import getCarMakes, getCarModels, getPermits

class Individual:
    def __init__(self, id, year, acadYear):
        #Query the information about the person
        personSQL = (
            ' SELECT DISTINCT'
            '   IDrec.id, TRIM(IDrec.firstname) AS firstname, TRIM(IDrec.lastname) AS lastname, TRIM(SRVrec.bldg) AS bldg'
            ' FROM'
            '   id_rec	IDrec	INNER JOIN	stu_serv_rec	SRVrec	ON	IDrec.id		    =	SRVrec.id'
            '                                                       AND	SRVrec.yr		    =	%s'
            ' WHERE'
            '   IDrec.id  =   %s'
        ) % (year, id)
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
            '   VEHrec.veh_no, VEHrec.model_yr, TRIM(INITCAP(VEHrec.make)) AS make, TRIM(INITCAP(VEHrec.model)) AS model, VEHrec.license, VEHrec.st_plate, PRKrec.permt_no AS permitId,'
            '   PRKrec.lotcode, PRKrec.permit_code, TRIM(PRKrec.permtcmmnt) AS permitcomment, TO_CHAR(PRKrec.active_date, "%%m/%%d/%%Y") AS active_date, TO_CHAR(PRKrec.inactive_date, "%%m/%%d/%%Y") AS inactive_date, TRIM(STKrec.permit_txt) AS permit_txt'
            ' FROM'
            '	veh_rec	VEHrec	LEFT JOIN	prkgpermt_rec	PRKrec	ON	VEHrec.veh_no		=	PRKrec.veh_no'
            '			        LEFT JOIN	prkgstckr_rec	STKrec	ON	PRKrec.permit_code	=	STKrec.permit_stckrcd'
            '							    						AND	VEHrec.acadyr		=	STKrec.permit_acadyr'
            ' WHERE'
            '   TODAY       BETWEEN VEHrec.issued_date AND NVL(VEHrec.inactive_date, TODAY)'
            '   AND'
            '   VEHrec.id       =   %s'
            '   AND'
            '   VEHrec.acadyr	=	"%s"'
            ' ORDER BY PRKrec.permt_no'
        ) % (id, acadYear)

        vehicles = do_sql(vehicleSQL).fetchall()
        self.vehicle = []
        
        #Loop through the vehicle records and attach the information to the person's record.
        for vehicle in vehicles:
            #permits = getPermits(vehicle.lotcode, acadYear)
            stickerSQL = (
                ' SELECT TRIM(permit_txt) AS permit_txt'
                ' FROM prkgstckr_rec'
                ' WHERE LOWER(permit_assocdlot) = LOWER("%s")'
                ' AND (permt_stat = "" OR LOWER(permit_txt) = LOWER("%s"))'
                ' AND permit_acadyr = "%s"'
                ' ORDER BY permit_txt'
            ) % (vehicle.lotcode, vehicle.permit_txt, acadYear)
            stickers = do_sql(stickerSQL).fetchall()
            
            #Include the list of makes for the vehicle's year so that the dropdowns can be loaded properly.
            matchedMakesSQL = (
                ' SELECT DISTINCT'
                '   INITCAP(TRIM(make_code)) AS make_code'
                ' FROM'
                '   vehmodel_table'
                ' WHERE'
                '   startyr >       %s'
                '   AND'
                '   %s      BETWEEN startyr AND NVL(endyr, %s)'
                ' ORDER BY make_code'
            ) % (1900, vehicle.model_yr, vehicle.model_yr)
            makes = do_sql(matchedMakesSQL).fetchall()
            #makes = getCarMakes(1900, vehicle.model_yr, vehicle.model_yr)

            #Include the list of models for the vehicle's year so that the dropdowns can be loaded properly.
            matchedModelsSQL = (
                ' SELECT DISTINCT'
                '   INITCAP(TRIM(model_code)) AS model_code'
                ' FROM'
                '   vehmodel_table'
                ' WHERE'
                '   startyr >       %s'
                '   AND'
                '   %s      BETWEEN startyr AND NVL(endyr, %s)'
                '   AND'
                '   TRIM(LOWER(make_code))  =   "%s"'
                ' ORDER BY model_code'
            ) % (1900, vehicle.model_yr, vehicle.model_yr, vehicle.make.lower())
            models = do_sql(matchedModelsSQL).fetchall()
            #models = getCarModels(1900, vehicle.model_yr, vehicle.model_yr, vehicle.make)
            self.vehicle.append(Vehicle(vehicle, stickers, makes, models))

class Vehicle:
    def __init__(self, vehicleObject, stickers, makes, models):
        self.veh_no = vehicleObject.veh_no
        self.model_yr = vehicleObject.model_yr
        self.make = vehicleObject.make
        self.model = vehicleObject.model
        self.license = vehicleObject.license
        self.st_plate = vehicleObject.st_plate
        self.permitId = vehicleObject.permitId
        self.lotcode = vehicleObject.lotcode
        self.permit_code = vehicleObject.permit_code
        self.permitcomment = vehicleObject.permitcomment
        self.active_date = vehicleObject.active_date
        self.inactive_date = vehicleObject.inactive_date
        self.permit_txt = vehicleObject.permit_txt
        self.stickers = stickers
        self.makes = makes
        self.models = models