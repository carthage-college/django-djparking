import json #added to support ajax calls
import re
#custom objects defined in __init__.py
from . import Individual, Stickers, Sticker, Permit, Makes, Models, Vehicle
from datetime import date, datetime, timedelta
from django.conf import settings
from django.core import serializers #added to support ajax calls
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext, loader, Context

#from djtools.utils.mail import send_mail
from django.core.mail import send_mail
#Creates connection to informix
from djzbar.utils.informix import do_sql

import simplejson

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
    year = '20' + search['acadYear'][0:2]
    if date.today().month <= 5:
        year = '20' + search['acadYear'][2:4]
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
        individual = Individual(search['ID'], year, search['acadYear'])
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

    if request.POST.get('carMake').lower() == 'zzgenericmake':
        email_data = {'actionType':'created','comment':request.POST.get('permitComment')}
        """
        send_mail(
            None, ['mkishline@carthage.edu'], 'Generic vehicle in Parking Admin', 'confirmation@carthage.edu',
            'manager/email_genericvehicle.html', email_data
        )
        """

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
            if request.POST.get('permitstatus') == '' or request.POST.get('permitstatus') == None:
                vehicleUpdate = permitUpdate(
                    request.POST.get('permit_no'),
                    request.POST.get('active_date'),
                    request.POST.get('inactive_date'),
                    request.POST.get('permitComment')
                )
                
                #assignSticker(sticker_txt, veh_no, active_date, permit_no = None, inactive_date = None, permit_comment = ''):
                
                """
                assignStickerNoInsert(
                    request.POST.get('sticker'),
                    request.POST.get('veh_no'),
                    request.POST.get('permit_no'),
                    request.POST.get('active_date')
                )
                """
                assignSticker(
                    request.POST.get('sticker'),
                    request.POST.get('veh_no'),
                    request.POST.get('active_date'),
                    request.POST.get('permit_no')
                )
            else:
                #If a sticker already exists for the vehicle
                if veh.permitid != None and veh.permitid > 0:
                    #Get the existing sticker attached to the record
                    sticker = Sticker(veh.permit_code, veh.acad_yr).updateStatus(request.POST.get('permitstatus'))
                    #Change the sticker's status
                    #sticker.updateStatus(request.POST.get('permitstatus'))
                    #Inactivate the parking permit record (also clears a lotloctn space)
                    old_permit = Permit(veh.permitid).inactivate()

                #Assign the sticker to the vehicle (creates the permit record)
                """
                assignStickerToVehicle(
                    request.POST.get('sticker'),
                    request.POST.get('veh_no'),
                    request.POST.get('active_date'),
                    request.POST.get('inactive_date'),
                    request.POST.get('permitComment')
                )
                """
                assignSticker(
                    request.POST.get('sticker'),
                    request.POST.get('veh_no'),
                    request.POST.get('active_date'),
                    request.POST.get('permit_no'),
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
def getLots(isResident = None, isInApt = None, isMotorcycle = None, includeFull = False):
    if isMotorcycle == True or isMotorcycle == 'true':
        lotSQL = (
            ' SELECT TRIM(lot.lotcode) AS lotcode, TRIM(lot.txt) AS txt, 0 AS spots'
            ' FROM  lot_table lot'
            ' WHERE TODAY       BETWEEN lot.active_date AND NVL(lot.inactive_date, TODAY)'
            ' AND   lot.lotcode     =   "MCYC"'
        )
    else:
        lotSQL = (' SELECT  TRIM(spaces.lotcode) AS lotcode, TRIM(lot.txt) AS txt, COUNT(spaces.lotloctn) AS spots'
                  ' FROM    lot_table   lot INNER JOIN  prkglot_rec spaces  ON  lot.lotcode =   spaces.lotcode'
                  ' WHERE   TODAY            BETWEEN    lot.active_date     AND NVL(lot.inactive_date, TODAY)'
                  #' AND     spaces.lot_stat    =        ""'
                  ' AND'
                  ' ('
                 )

        #Check if arguments were passed into the function
        if isResident != None:
            #If the individual is a campus resident they have access to
            #all lots besides Commuter, Lot S, and the virtual Motorcycle lot
            if isResident == 'true' or isResident == True:
                lotSQL += ' lot.lotcode NOT IN ("CMTR","LOTS","MCYC")'
                #Individuals who live in the apartments are allowed to buy a permit for Lot S
                if isInApt == True or isInApt == 'true':
                    lotSQL += ' OR lot.lotcode = "LOTS"'
            else:
                lotSQL += ' lot.lotcode = "CMTR"'

        lotSQL += ') GROUP BY spaces.lotcode, lot.txt'
        #if not includeFull or includeFull == 'false':
        #    lotSQL += ' HAVING COUNT(spaces.lotloctn) > 0'
        lotSQL += ' ORDER BY TRIM(lot.txt)'

    try:
        lot_results = do_sql(lotSQL).fetchall()
    except:
        lot_results = lotSQL
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
        "    TRIM(lot_table.txt) lot_txt,"
        "    CASE TRIM(lot_rec.lot_stat)"
        "        WHEN    'A'    THEN    'Allocated/Sold'"
        "        WHEN    ''     THEN    'Available'"
        "        WHEN    'S'    THEN    'Held in Reserve'"
        "        WHEN    'R'    THEN    'Reserved (dumpsters/construction)'"
        #"        WHEN    'R'    THEN    'Dumpster'"
        "        WHEN    'H'    THEN    'Handicap'"
        "        WHEN    'W'    THEN    'Waitlist'"
        #"        WHEN    'F'    THEN    'Fleet Vehicle'"
        "    END AS status,"
        "    COUNT(*) AS spaces,"
        "    CASE"
        "        WHEN    NVL(lotSpaces.hasSpaces,0)    =    0    THEN    'Full'"
        "                                                    ELSE    'Available'"
        "    END    AS    lot_status"
        " FROM  prkglot_rec lot_rec INNER JOIN  lot_table   ON  lot_rec.lotcode     =   lot_table.lotcode"
        #"                                                   AND lot_rec.lot_acadyr  =   lot_table.acadyr"
        "                           LEFT JOIN    ("
        "                                SELECT lotcode, COUNT(*) hasSpaces"
        "                               FROM prkglot_rec"
        "                               WHERE lot_stat = ''"
        "                               AND lot_acadyr = '%s'"
        "                               GROUP BY lotcode"
        "                           )            lotSpaces    ON    lot_rec.lotcode    =    lotSpaces.lotcode"
        " WHERE TODAY BETWEEN lot_rec.active_date AND NVL(lot_rec.inactive_date, TODAY)"
        " AND TODAY BETWEEN lot_table.active_date AND NVL(lot_table.inactive_date, TODAY)"
        #" AND   acadyr  =   '%s'"
        " AND    lot_acadyr    =    '%s'"
        " AND   lot_rec.lot_stat    NOT IN  ('R','F')"
        " GROUP BY  lot_txt, lot_rec.lot_stat, lot_status"
        " ORDER BY  lot_txt, status"
    ) % (acadYear, acadYear)
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
            "       AND     lot_acadyr = '%s'"
            "   )"
        )   %   (vehicle.id, veh_no, sticker.permit_assocdlot, sticker.permit_assocdlot, vehicle.acad_yr)
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

def assignStickerNoInsert(sticker_txt, veh_no, permit_no, active_date):
    vehicle = Vehicle().loadByID(veh_no)
    
    selectStickerSQL = (
        " SELECT stckr.*"
        " FROM prkgstckr_rec stckr"
        " WHERE stckr.permit_txt = '%s'"
        " AND stckr.permt_stat = ''"
    ) % (sticker_txt)
    sticker_results = do_sql(selectStickerSQL)
    
    if sticker_results != None:
        sticker_current = sticker_results.fetchone()
        
        updateStickerSQL = (
            " UPDATE prkgstckr_rec"
            " SET permt_stat = 'A'"
            " , issue_date = '%s'"
            " WHERE"
            " permit_stckrcd = '%s'"
        ) % (active_date, sticker_current.permit_stckrcd)
        do_sql(updateStickerSQL)
        
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
        )   %   (vehicle.id, veh_no, sticker_current.permit_assocdlot, sticker_current.permit_assocdlot)
        do_sql(consumeLotLocationSQL)

        getLotLocationSQL = (
            " SELECT prkglot_rec.*"
            " FROM prkglot_rec"
            " WHERE lotcmmnt = '%s,%s'"
        ) % (vehicle.id, veh_no)
        lot_loc = do_sql(getLotLocationSQL).fetchone()
        
        updatePermitSQL = (
            " UPDATE prkgpermt_rec"
            " SET lotcode = '%s'"
            " , lotloctn = '%s'"
            " , permit_code = '%s'"
            " , permt_stat = 'A'"
            " WHERE permt_no = %s"
        ) % (sticker_current.permit_assocdlot, lot_loc.lotloctn, sticker_current.permit_stckrcd, permit_no)
        do_sql(updatePermitSQL)

def assignSticker(sticker_txt, veh_no, active_date, permit_no = 0, inactive_date = None, permit_comment = ''):
    vehicle = Vehicle().loadByID(veh_no)
    
    selectStickerSQL = (
        " SELECT stckr.*"
        " FROM prkgstckr_rec stckr"
        " WHERE stckr.permit_txt = '%s'"
        " AND stckr.permt_stat = ''"
    ) % (sticker_txt)
    sticker_results = do_sql(selectStickerSQL)
    
    if sticker_results != None:
        sticker_current = sticker_results.fetchone()
        
        updateStickerSQL = (
            " UPDATE prkgstckr_rec"
            " SET permt_stat = 'A'"
            " , issue_date = '%s'"
            " WHERE"
            " permit_stckrcd = '%s'"
            " AND permit_acadyr = '%s'"
        ) % (active_date, sticker_current.permit_stckrcd, vehicle.acad_yr)
        do_sql(updateStickerSQL)

        getLotLocationSQL = (
            " SELECT"
            "    FIRST 1 lotloctn"
            " FROM"
            "    ("
            "        SELECT"
            "            lot_rec.lotloctn,"
            "            CASE"
            "                WHEN    lot_rec.lot_stat    =    'A' THEN    0"
            "                                                   ELSE    lot_rec.lotloctn::integer"
            "            END AS priority"
            "        FROM"
            "            prkglot_rec    lot_rec    LEFT JOIN    prkgpermt_rec    permit_rec    ON    lot_rec.lotcode        =    permit_rec.lotcode"
            "                                                                        AND    lot_rec.lot_acadyr    =    permit_rec.acadyr"
            "                                                                        AND    lot_rec.lotloctn    =    permit_rec.lotloctn"
            "        WHERE"
            "            lot_rec.lotcode        =    '%s'"
            "            AND"
            "            lot_rec.lot_acadyr    =    '%s'"
            "            AND"
            "            ("
            "                lot_rec.lot_stat    =    ''"
            "                OR"
            "                ("
            "                    lot_rec.lot_stat    =    'A'"
            "                    AND"
            "                    permit_rec.permt_no    IS    NOT NULL"
            "                    AND"
            "                    permit_rec.permt_no    =    %s"
            "                )"
            "            )"
            "        ORDER BY lot_stat DESC, lot_rec.lotloctn"
            "    )"
        ) % (sticker_current.permit_assocdlot, vehicle.acad_yr, permit_no)
        lot_loc = do_sql(getLotLocationSQL).first()

        consumeLotLocationSQL = (
            " UPDATE prkglot_rec"
            " SET lot_stat = 'A'"
            " , lotcmmnt = '%s,%s'"
            " WHERE"
            "   lotcode = '%s'"
            "   AND"
            "   lot_acadyr = '%s'"
            "   AND"
            "    lotloctn = '%s'"
            #"   lotloctn = ("
            #"       SELECT MIN(lotloctn)"
            #"       FROM    prkglot_rec"
            #"       WHERE   lotcode = '%s'"
            #"       AND     lot_stat = ''"
            #"       AND     lot_acadyr = '%s'"
            #"   )"
        )   %   (vehicle.id, veh_no, sticker_current.permit_assocdlot, vehicle.acad_yr, lot_loc.lotloctn)
        #)   %   (vehicle.id, veh_no, sticker_current.permit_assocdlot, vehicle.acad_yr, sticker_current.permit_assocdlot, vehicle.acad_yr)
        do_sql(consumeLotLocationSQL)

        """
        getLotLocationSQL = (
            " SELECT prkglot_rec.*"
            " FROM prkglot_rec"
            " WHERE lotcmmnt = '%s,%s'"
            " AND lot_acadyr = '%s'"
        ) % (vehicle.id, veh_no, vehicle.acad_yr)
        #lot_loc = do_sql(getLotLocationSQL).fetchone()
        lot_loc = do_sql(getLotLocationSQL).first()
        """
        
        if vehicle.id == 1319170:
            send_mail("Debug parking",
                "Student: %s\n permit_no: %s\n lotloctn: %s\n int permit number is 0: %s" % (vehicle.id, permit_no, lot_loc.lotloctn, int(permit_no) == 0),
                "confirmation@carthage.edu",['mkishline@carthage.edu'],
                fail_silently=True
            )
        
        if permit_no == 0:
            permitSQL = (
                " INSERT INTO prkgpermt_rec (lotcode, lotloctn, permit_code, acadyr, permt_id, veh_no, permt_stat, active_date, inactive_date, permtcmmnt)"
                " VALUES ('%s', '%s', '%s', '%s', %s, %s, '%s', '%s', '%s', '%s')"
            ) % (sticker.permit_assocdlot, lot_loc.lotloctn, sticker.permit_stckrcd, vehicle.acad_yr, vehicle.id, veh_no, 'A', active_date, inactive_date, permit_comment)
        else:
            permitSQL = (
                " UPDATE prkgpermt_rec"
                " SET lotcode = '%s'"
                " , lotloctn = '%s'"
                " , permit_code = '%s'"
                " , permt_stat = 'A'"
                " WHERE permt_no = %s"
            ) % (sticker_current.permit_assocdlot, lot_loc.lotloctn, sticker_current.permit_stckrcd, permit_no)

        if vehicle.id == 1319170:
            send_mail("Debug parking SQL","%s" % (permitSQL), 'confirmation@carthage.edu', ['mkishline@carthage.edu'], fail_silently=True)
        do_sql(permitSQL)

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
    Permit(vehicle.permitid).inactivate()

    return None

def expireVehicle(veh_no):
    vehicleExpireSQL = (
        " UPDATE veh_rec"
        " SET inactive_date = TODAY"
        " WHERE veh_no = %s"
    ) % (veh_no)
    do_sql(vehicleExpireSQL)
    return veh_no

def ajaxLots(request):
    isResident = request.GET.get('isResident')
    isInApt = request.GET.get('isInApt')
    isMotorcycle = request.GET.get('isMotorcycle')
    
    lot_results = getLots(isResident, isInApt, isMotorcycle)
    jsonDump = []
    try:
        for lot in lot_results:
            tmpdict = {'lotcode':lot.lotcode,'txt':lot.txt}
            jsonDump.append(tmpdict)
    except Exception as e:
        jsonDump.append({'lotcode':'none','txt':lot_results})

    return HttpResponse(simplejson.dumps(jsonDump), content_type="application/json")

def ajaxCarMakes(request):
    #Retrieve the list of car makes for a specific year
    makes = Makes().getByYear(request.GET.get('year'))
    
    #Create string of makes delimited by a ','
    tmp = ','.join([make.make_code for make in makes])
    return HttpResponse(simplejson.dumps(tmp), content_type="applicaton/json")

def ajaxCarModels(request):
    year = request.GET.get('year')
    make = request.GET.get('make')

    #Retrieve the list of models given the year and make of the car
    models = Models().getByYearMake(year, make)
    
    #Create string of models delimited by a ","
    tmp = ''
    if len(models):
        tmp = ','.join([model.model_code for model in models])
    return HttpResponse(simplejson.dumps(tmp), content_type="application/json")

def ajaxStickers(request):
    lotcode = request.GET.get('lotcode')
    acadYear = request.GET.get('acadYear')
    originalSticker = request.GET.get('originalSticker')
    stickers = Stickers().forLot(lotcode, acadYear, originalSticker)
    tmp = ','.join([sticker.permit_txt for sticker in stickers])
    return HttpResponse(simplejson.dumps(tmp), content_type="application/json")

#def ajaxSearch(request, acadYear):
def ajaxSearch(request):
    
    acadYear = request.GET.get('acadYear')
    
    #The jQueryUI autocomplete widget passes its value as a GET variable called "term"
    searchTerm = request.GET.get('term')
    #Academic year is passed as part of the URL. Since academic years are a concatenation of the last two digits of the years (ie 1314 = 2013-2014)
    #we simply take the first two characters and prepend "20" resulting in "2013"
    thisYear = '20' + acadYear[0:2]
    if date.today().month <= 5:
        thisYear = '20' + acadYear[2:4]

    searchSQL = (
        ' SELECT'
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

    #Add grouping to filter out duplicates and sorting so multiple results are more easily viewed by user
    searchSQL += (
        ' GROUP BY value, id, IDrec.lastname, IDrec.firstname'
        ' ORDER BY IDrec.lastname, IDrec.firstname'
    )

    #Create a serializable entity with the results from the query
    jsonDump = []

    try:
        search_results = do_sql(searchSQL).fetchall()
    
        for result in search_results:
            tmpdict = {'id':result.id,'value':result.value}
            jsonDump.append(tmpdict)
    except:
        jsonDump = searchSQL

    return HttpResponse(simplejson.dumps(jsonDump), content_type="application/json")
