import json #added to support ajax calls
import re
from . import Individual, Stickers, Sticker, Permit, Makes, Models, Vehicle #custom objects defined in __init__.py
from datetime import date, datetime
from django.conf import settings
from django.core import serializers #added to support ajax calls
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext, loader, Context
from django.utils import simplejson

from djtools.utils.mail import send_mail
#Creates connection to informix
from djzbar.utils.informix import do_sql

if settings.DEBUG:
    TO_LIST = ["mkishline@carthage.edu",]
else:
    TO_LIST = ["mkishline@carthage.edu",]
BCC = settings.MANAGERS

def search(request, redir_acad_yr = None, redir_txt = '', redir_id = 0):
    thisYear = date.today().year - 1
    if date.today().month >= 4:
        thisYear = thisYear + 1
    acadYearRange = range(2012, thisYear + 1)
    acadYear = '%s%s' % (thisYear % 100, (thisYear % 100) + 1)

    acadYearList = []
    for yr in acadYearRange:
        val = '%s%s' % (yr % 100, (yr % 100) + 1)
        txt = '%s-%s' % (yr, yr + 1)
        acadYearList.append([val, txt])

    search = {'year':thisYear,'acadYear':acadYear,'ID':0,'text':''}
    carYears = getCarYears()
    states = getStates()
    lots = []

    individual = None
    personSQL = ''
    debugvar = ''
    if request.method == 'POST':
        search['acadYear'] = request.POST.get('academicYear')
        search['text'] = request.POST.get('searchText')
        search['ID'] = request.POST.get('searchID')
    elif redir_acad_yr != None:
        search['acadYear'] = redir_acad_yr
        search['text'] = redir_txt
        search['ID'] = redir_id

    isSearched = False
    if search['ID'] > 0:
        isSearched = True
        individual = Individual(search['ID'], '20' + search['acadYear'][0:2], search['acadYear'])
        lots = getLots(individual.bldg != 'CMTR', individual.bldg == 'APT')

    summary = getLotSummary(search['acadYear'])

    return render_to_response(
        "manager/search.html", {
            'years':acadYearList,'search':search,'currentAcadYear':acadYear,
            'person':individual,'isSearched':isSearched,
            'lots':lots,'states':states,'summary':summary,'carYears':carYears,
            'present':date.today(),'debug':'%s' % (debugvar)
        },
        context_instance=RequestContext(request)
    )

def create(request):
    #Create a vehicle record and associate it with a user
    vehicleInsert = addVehicle(
        request.POST.get('studentId'),
        request.POST.get('license'),
        request.POST.get('st_plate'),
        request.POST.get('carMake'),
        request.POST.get('carModel'),
        request.POST.get('carYear'),
        request.POST.get('acadYear')
    )
    #If a sticker was specified and the status was changed, create the permit record
    if request.POST.get('sticker') != '' and request.POST.get('sticker') != None:
        assignStickerToVehicle(
            request.POST.get('sticker'),
            vehicleInsert,
            request.POST.get('active_date'),
            request.POST.get('inactive_date'),
            request.POST.get('permitComment')
        )

    """
    return render_to_response(
        "manager/success.html",
        {'debug':vehicleInsert },
        context_instance=RequestContext(request)
    )
    """
    return HttpResponseRedirect(reverse('manager_search_redirect', kwargs={'redir_id':request.POST.get('studentId'),'redir_acad_yr':request.POST.get('acadYear')}))

def update(request):
    if request.POST.get('takeAction') == "update":
        #Update the vehicle record
        vehicleUpdate = updateVehicle(
            request.POST.get('veh_no'),
            request.POST.get('license'),
            request.POST.get('st_plate'),
            request.POST.get('carMake'),
            request.POST.get('carModel'),
            request.POST.get('carYear')
        )
        veh = Vehicle().loadByID(int(vehicleUpdate))
        #If a sticker was specified, create the permit record
        if request.POST.get('sticker') != '' and request.POST.get('sticker') != None:
            if request.POST.get('permitStatus') == '' or request.POST.get('permitStatus') == None:
                vehicleUpdate = permitUpdate(
                    request.POST.get('permit_no'),
                    request.POST.get('active_date'),
                    request.POST.get('inactive_date'),
                    request.POST.get('permitComment')
                )
            else:
                #If a sticker already exists for the vehicle
                if veh.permitId != None:
                    #Get the existing sticker attached to the record
                    sticker = Sticker(veh.permit_code, veh.acad_yr)
                    #Change the sticker's status
                    sticker.updateStatus(request.POST.get('permitStatus'))
                    #Inactivate the parking permit record (also clears a lotloctn space)
                    old_permit = Permit(veh.permitId).inactivate()
                
                #Assign the sticker to the vehicle (creates the permit record)
                assignStickerToVehicle(
                    request.POST.get('sticker'),
                    vehicleUpdate,
                    request.POST.get('active_date'),
                    request.POST.get('inactive_date'),
                    request.POST.get('permitComment')
                )

    elif request.POST.get('takeAction') == "delete":
        #vehicleUpdate = expireVehicle(request.POST.get('veh_no'))
        vehicleUpdate = "Delete"
    else:
        vehicleUpdate = ("Action '%s' did not match") % (request.POST.get('takeAction'))
    
    """
    return render_to_response(
        "manager/success.html",
        {'debug':vehicleUpdate},
        context_instance=RequestContext(request)
    )
    """
    return HttpResponseRedirect(reverse('manager_search_redirect', kwargs={'redir_id':request.POST.get('searchID'),'redir_acad_yr':request.POST.get('academicYear')}))

#Get the collection of lots that are available to an individual given their residency information
def getLots(isResident = None, isInApt = None, includeFull = False):
    lotSQL = (' SELECT    TRIM(spaces.lotcode)    lotcode, TRIM(lot.txt)    txt, COUNT(spaces.lotloctn) spots, lot.cost'
              ' FROM    lot_table    lot INNER JOIN    prkglot_rec    spaces    ON    lot.lotcode    =    spaces.lotcode'
              ' WHERE    TODAY            BETWEEN    lot.active_date    AND    NVL(lot.inactive_date, TODAY)'
              ' AND        spaces.lot_stat    =        ""'
              ' AND'
              ' ('
             )

    #Check if arguments were passed into the function
    if isResident != None:
        #If the individual is a campus resident they have access to
        #all lots besides Commuter and Lot S
        if isResident:
            lotSQL += ' lot.lotcode NOT IN ("CMTR","LOTS")'
            #Individuals who live in the apartments are allowed
            #to buy a permit for Lot S
            if isInApt:
                lotSQL += ' OR lot.lotcode = "LOTS"'
        else:
            lotSQL += ' lot.lotcode = "CMTR"'
    lotSQL += ') GROUP BY spaces.lotcode, lot.txt, lot.cost'
    if not includeFull:
        lotSQL += ' HAVING COUNT(spaces.lotloctn) > 0'
    lotSQL += ' ORDER BY TRIM(lot.txt)'
    lot_results = do_sql(lotSQL).fetchall()
    return lot_results

def getCarYears(minYear = 1900):
    return range(1947, date.today().year + 2)

#Get the list of states to be used in the drop down lists
def getStates():
    stateSQL = (
        ' SELECT TRIM(st) AS st, TRIM(txt) AS txt'
        ' FROM st_table'
        ' WHERE low_zone > 0'
        ' AND high_zone > 0'
        ' ORDER BY txt'
    )
    return do_sql(stateSQL).fetchall()

def getLotSummary(acadYear):
    summarySQL = (
        " SELECT"
        "    TRIM(lot_table.txt) lotTxt,"
        "    CASE TRIM(lot_rec.lot_stat)"
        "        WHEN    'A'    THEN    'Allocated/Sold'"
        "        WHEN    ''     THEN    'Available'"
        "        WHEN    'S'    THEN    'Held in Reserve'"
        #"        WHEN    'R'    THEN    'Reserved (dumpsters/construction)'"
        #"        WHEN    'R'    THEN    'Dumpster'"
        "        WHEN    'H'    THEN    'Handicap'"
        "        WHEN    'W'    THEN    'Waitlist'"
        #"        WHEN    'F'    THEN    'Fleet Vehicle'"
        "    END AS status,"
        "    COUNT(*) AS spaces"
        " FROM  prkglot_rec lot_rec INNER JOIN  lot_table   ON  lot_rec.lotcode     =   lot_table.lotcode"
        "                                                   AND lot_rec.lot_acadyr  =   lot_table.acadyr"
        " WHERE TODAY BETWEEN lot_rec.active_date AND NVL(lot_rec.inactive_date, TODAY)"
        " AND   acadyr  =   '%s'"
        " AND   lot_rec.lot_stat    NOT IN  ('R','F')"
        " GROUP BY  lotTxt, lot_rec.lot_stat"
        " ORDER BY  lotTxt, status"
    ) % (acadYear)
    return do_sql(summarySQL).fetchall()

#SQL commented out to prevent accidental inserts
def addVehicle(id, license, st_plate, make, model, model_yr, acadyr):
    insertVehicleSQL = (
        " INSERT INTO veh_rec (id, license, st_plate, make, model, model_yr, acadyr, issued_date)"
        " VALUES (%s, '%s', '%s', '%s', '%s', %s, '%s', TODAY)"
    ) % (id, license, st_plate, make, model, model_yr, acadyr)
    do_sql(insertVehicleSQL)
    #getVehicleSQL = ("SELECT DISTINCT dbinfo('sqlca.sqlerrd1') AS veh_no FROM veh_rec")
    getVehicleSQL = ("SELECT veh_no FROM veh_rec WHERE id = %s AND license = '%s' AND acadyr = '%s'") % (id, license, acadyr)
    veh_results = do_sql(getVehicleSQL).fetchone()
    return veh_results.veh_no
    #return insertVehicleSQL

def updateVehicle(veh_no, license, st_plate, make, model, model_yr):
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

def reserveSpot(acadYear, lot):
    getNextSQL = (
        " SELECT"
        "   lotcode, MIN(lot_no) AS lot_no, MIN(lotloctn) AS lotloctn"
        " FROM"
        "   prkglot_rec"
        " WHERE"
        "   TODAY   BETWEEN active_date AND NVL(inactive_date, TODAY)"
        "   AND"
        "   TRIM(lot_stat)  =   ''"
        "   AND"
        "   lot_acadyr  =   '%s'"
        "   AND"
        "   lotcode =   '%s'"
        " GROUP BY lotcode"
    ) % (acadYear, lot)
    getNext = do_sql(getNextSQL).fetchone()
    reserveSpotSQL = (
        " UPDATE prkglot_rec"
        " SET lot_stat  =   'A'"
        " WHERE"
        "   lot_no      =   %s"
    ) % (getNext.lot_no)
    do_sql(reserveSpotSQL)
    return getNext.lot_no
    #return ("%s<br /><br />%s") % (getNextSQL, reserveSpotSQL)

def assignPermit(id, veh_no, nextSpot, acadYear):
    insertPermitSQL = (
        " INSERT INTO prkgpermt_rec"
        "   (lotcode, lotloctn, permit_code, acadyr, permt_id, veh_no, permt_stat, active_date, permtcmmnt)"
        " VALUES ('%s', '%s', '%s', '%s', %s, %s, '%s', '%s', '%s')"
    ) % (nextSpot.lotcode, nextSpot.lotloctn, '', acadYear, id, veh_no, '', TODAY, '')
    do_sql(insertPermitSQL)

def permitUpdate(permit_no, active_date, inactive_date, comment):
    updatePermitSQL = (
        " UPDATE prkgpermt_rec"
        " SET active_date = '%s',"
        "     inactive_date = '%s',"
        "     permtcmmnt = '%s'"
        " WHERE permt_no = %s"
    ) % (active_date, inactive_date, comment, permit_no)
    do_sql(updatePermitSQL)
    return updatePermitSQL

def assignStickerToVehicle(sticker_txt, veh_no, active_date, inactive_date = None, permit_comment = ''):
    #Get vehicle record
    vehicle = Vehicle().loadByID(veh_no)

    #Get sticker record
    selectStickerSQL = (
        " SELECT sticker.*"
        " FROM prkgstckr_rec sticker"
        " WHERE sticker.permit_txt = '%s'"
        " AND sticker.permt_stat = ''"
    ) % (sticker_txt)
    sticker_results = do_sql(selectStickerSQL)

    if sticker_results != None:
        sticker = sticker_results.fetchone()
        
        #Update prkgstckr_rec (flag sticker as sold)
        updateStickerSQL = (
            " UPDATE prkgstckr_rec"
            " SET permt_stat = 'A'"
            " , issue_date = '%s'"
            " WHERE"
            " permit_stckrcd = '%s'"
            ) % (active_date, sticker.permit_stckrcd)
        do_sql(updateStickerSQL)

        #Get the next available spot in the lot
        consumeLotLocationSQL = (
            " UPDATE prkglot_rec"
            " SET lot_stat = 'A'"
            " , lotcmmnt = '%s,%s'"
            " WHERE"
            "   lotcode = '%s'"
            "   AND"
            "   lotloctn = ("
            "       SELECT MIN(lotloctn)"
            "       FROM    prkglot_rec"
            "       WHERE   lotcode = '%s'"
            "       AND     lot_stat = ''"
            "   )"
        )   %   (vehicle.id, veh_no, sticker.permit_assocdlot, sticker.permit_assocdlot)
        do_sql(consumeLotLocationSQL)

        #Get lot location detail
        getLotLocationSQL = (
            " SELECT prkglot_rec.*"
            " FROM prkglot_rec"
            " WHERE lotcmmnt = '%s,%s'"
        ) % (vehicle.id, veh_no)
        lot_loc = do_sql(getLotLocationSQL).fetchone()

        #Create prkgpermt_rec record
        insertPermitSQL = (
            " INSERT INTO prkgpermt_rec (lotcode, lotloctn, permit_code, acadyr, permt_id, veh_no, permt_stat, active_date, inactive_date, permtcmmnt)"
            " VALUES ('%s', '%s', '%s', '%s', %s, %s, '%s', '%s', '%s', '%s')"
        ) % (sticker.permit_assocdlot, lot_loc.lotloctn, sticker.permit_stckrcd, vehicle.acad_yr, vehicle.id, veh_no, 'A', active_date, inactive_date, permit_comment)
        do_sql(insertPermitSQL)

    else:
        return -1

    return None

def removeStickerFromVehicle(permit_status, veh_no):
    #Update prkgpermt_rec (set inactive date)
    #Update prkgstckr_rec (flag sticker as S=Surrender, L=Lost, D=Damaged/Destroyed)
    
    #Get vehicle information (to be used in sticker query)
    vehicle = Vehicle().loadByID(veh_no)

    #Update sticker status
    """
    updateStickerSQL = (
        " UPDATE prkgstckr_rec"
        " SET permt_stat = '%s'"
        " , inactive_date = TODAY"
        " WHERE permit_stckrcd = '%s'"
        " AND permit_acadyr = '%s'"
    ) % (permit_status, vehicle.permit_code, vehicle.acad_yr)
    do_sql(updateStickerSQL)
    """
    Sticker(vehicle.permit_code, vehicle.acad_yr).updateStatus(permit_status)

    """
    updatePermitSQL = (
        " UPDATE prkgpermt_rec"
        " SET inactive_date = TODAY"
        " WHERE veh_no = %s"
    ) % (veh_no)
    """
    Permit(vehicle.permitId).inactivate()

    return None

def expireVehicle(veh_no):
    vehicleExpireSQL = (
        " UPDATE veh_rec"
        " SET inactive_date = TODAY"
        " WHERE veh_no = %s"
    ) % (veh_no)
    do_sql(vehicleExpireSQL)
    return veh_no

#def ajaxLots(request, isMotorcycle, isResident, isInApt, includeFull):
#    if isMotorcycle:

def ajaxCarMakes(request, year):
    #Retrieve the list of car makes for a specific year
    #makes = getCarMakes(year)
    makes = Makes().getByYear(year)
    
    #Create string of makes delimited by a ","
    tmp = ','.join([make.make_code for make in makes])
    return HttpResponse(simplejson.dumps(tmp), content_type="application/json")

def ajaxCarModels(request, year, make):
    #Retrieve the list of models given the year and make of the car
    #models = getCarModels(year, make)
    models = Models().getByYearMake(year, make)
    
    #Create string of models delimited by a ","
    tmp = ','.join([model.model_code for model in models])
    return HttpResponse(simplejson.dumps(tmp), content_type="application/json")

def ajaxStickers(request, lotcode, acadYear):
    stickers = Stickers().forLot(lotcode, acadYear)
    tmp = ','.join([sticker.permit_txt for sticker in stickers])
    return HttpResponse(simplejson.dumps(tmp), content_type="application/json")

def ajaxSearch(request, acadYear):
    #The jQueryUI autocomplete widget passes its value as a GET variable called "term"
    searchTerm = request.GET.get('term')
    #Academic year is passed as part of the URL. Since academic years are a concatenation of the last two digits of the years (ie 1314 = 2013-2014)
    #we simply take the first two characters and prepend "20" resulting in "2013"
    thisYear = '20' + acadYear[0:2]

    searchSQL = (
        ' SELECT DISTINCT'
        '    TRIM(IDrec.lastname) || ", " || TRIM(IDrec.firstname) || " (" || IDrec.id || ")" AS value, IDrec.id, IDrec.firstname, IDrec.lastname'
        ' FROM'
        '   id_rec  IDrec   INNER JOIN  stu_serv_rec    SRVrec  ON  IDrec.id            =   SRVrec.id'
        '                                                       AND SRVrec.yr           =   %s'
    ) % (thisYear)

    #Does the search term match the format of an ID? (numeric value of 4 characters or more)
    if re.match(r'\d{4,}', searchTerm) != None:
        searchSQL += ' WHERE IDrec.id    =   %s' % (searchTerm)
    #Does the search term match the format for a permit? (alpha character followed by an optional "-" and then 1 or more digits)
    elif re.match(r'[a-z]{1,2}\-?\d{1,}', searchTerm, re.I) != None:
        searchSQL += (
            '                   LEFT JOIN   veh_rec         VEHrec  ON  IDrec.id            =   VEHrec.id'
            '                                                       AND VEHrec.acadyr       =   "%s"'
            '                   LEFT JOIN   prkgpermt_rec   PRKrec  ON  VEHrec.veh_no       =   PRKrec.veh_no'
            '                   LEFT JOIN   prkgstckr_rec   STKrec  ON  PRKrec.permit_code  =   STKrec.permit_stckrcd'
            '                                                       AND VEHrec.acadyr       =   STKrec.permit_acadyr'
            ' WHERE LOWER(STKrec.permit_txt)    LIKE    LOWER("%s%%")'
        )   % (acadYear, re.sub(r'\-', '', searchTerm))
    #If neither of the above conditions are met, we assume the search term represents the last name
    else:
        searchSQL += ' WHERE LOWER(IDrec.lastname)   LIKE    LOWER("%s%%")' % (searchTerm)

    #Add sorting so multiple results are more easily viewed by user
    searchSQL += ' ORDER BY IDrec.lastname, IDrec.firstname'

    search_results = do_sql(searchSQL).fetchall()

    #Create a serializable entity with the results from the query
    jsonDump = []
    for result in search_results:
        tmpdict = {'id':result.id,'value':result.value}
        jsonDump.append(tmpdict)

    return HttpResponse(simplejson.dumps(jsonDump), content_type="application/json")
