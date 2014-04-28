import json #added to support ajax calls
import re
from . import Individual #custom object defined in __init__.py
from datetime import date
from django.conf import settings
from django.core import serializers #added to support ajax calls
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

def search(request):
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
    summary = getLotSummary(search['acadYear'])
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

        individual = Individual(
            search['ID'],
            '20' + search['acadYear'][0:2],
            search['acadYear']
        )
        lots = getLots(individual.bldg != 'CMTR', individual.bldg == 'APT')

    return render_to_response(
        "manager/search.html", {
            'years':acadYearList,'search':search,'currentAcadYear':acadYear,
            'person':individual,'isSearched':request.method == 'POST',
            'lots':lots,'states':states,'summary':summary,'carYears':carYears,
            'debug':'%s' % (debugvar)
        },
        context_instance=RequestContext(request)
    )

def create(request):
    vehicleInsert = addVehicle(
        request.POST.get('studentId'),
        request.POST.get('license'),
        request.POST.get('st_plate'),
        request.POST.get('carMake'),
        request.POST.get('carModel'),
        request.POST.get('carYear'),
        request.POST.get('acadYear')
    )
    return render_to_response(
        "manager/success.html",
        {'debug':vehicleInsert },
        context_instance=RequestContext(request)
    )

def update(request):
    if request.POST.get('takeAction') == "update":
        vehicleUpdate = updateVehicle(
            request.POST.get('veh_no'),
            request.POST.get('license'),
            request.POST.get('st_plate'),
            request.POST.get('carMake'),
            request.POST.get('carModel'),
            request.POST.get('carYear')
        )
    elif request.POST.get('takeAction') == "delete":
        vehicleUpdate = expireVehicle(request.POST.get('veh_no'))
    else:
        vehicleUpdate = ("Action '%s' did not match") % (request.POST.get('takeAction'))
    return render_to_response(
        "manager/success.html",
        {'debug':vehicleUpdate},
        context_instance=RequestContext(request)
    )

#Get the collection of lots that are available to an
#individual given their residency information
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

def getStickers(lotcode, acadYear):
    permitSQL = (
        ' SELECT TRIM(permit_txt) AS permit_txt'
        ' FROM prkgstckr_rec'
        ' WHERE LOWER(permit_assocdlot) = LOWER("%s")'
        ' AND permt_stat = ""'
        ' AND permit_acadyr = "%s"'
        ' ORDER BY permit_txt'
    ) % (lotcode, acadYear)
    return do_sql(permitSQL).fetchall()

#Get the list of car makers for a given year
def getCarMakes(year, minYear = 1900):
    carMakesSQL = (
        ' SELECT DISTINCT INITCAP(TRIM(make_code)) AS make_code'
        ' FROM vehmodel_table'
        ' WHERE startyr > %s'
        ' AND    %s  BETWEEN startyr AND NVL(endyr, %s)'
        ' ORDER BY make_code'
    ) % (minYear, year, year)
    return do_sql(carMakesSQL).fetchall()

#Get the list of models associated with a specified make within a limited year range
def getCarModels(year, make, minYear = 1900):
    carModelsSQL = (
        ' SELECT INITCAP(TRIM(model_code)) AS model_code'
        ' FROM vehmodel_table'
        ' WHERE startyr > %s'
        ' AND    %s  BETWEEN startyr AND NVL(endyr, %s)'
        ' AND    TRIM(LOWER(make_code))   =   LOWER("%s")'
        ' ORDER BY make_code, model_code'
    ) % (minYear, year, year, make)
    return do_sql(carModelsSQL).fetchall()

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
        "        WHEN    ''    THEN    'Available'"
        "        WHEN    'S'    THEN    'Held in Reserve'"
        "        WHEN    'R'    THEN    'Reserved (dumpsters/construction)'"
        "        WHEN    'H'    THEN    'Handicap'"
        "        WHEN    'W'    THEN    'Waitlist'"
        "        WHEN    'F'    THEN    'Fleet Vehicle'"
        "    END AS status,"
        "    COUNT(*) AS spaces"
        " FROM prkglot_rec lot_rec INNER JOIN lot_table ON lot_rec.lotcode = lot_table.lotcode"
        " WHERE TODAY BETWEEN lot_rec.active_date AND NVL(lot_rec.inactive_date, TODAY)"
        " AND acadyr = '%s'"
        " GROUP BY lotTxt, lot_rec.lot_stat"
        " ORDER BY lotTxt, status"
    ) % (acadYear)
    return do_sql(summarySQL).fetchall()

#SQL commented out to prevent accidental inserts
def addVehicle(id, license, st_plate, make, model, model_yr, acadyr):
    insertVehicleSQL = (
        " INSERT INTO veh_rec (id, license, st_plate, make, model, model_yr, acadyr, issued_date)"
        " VALUES (%s, '%s', '%s', '%s', '%s', %s, '%s', TODAY)"
    ) % (id, license, st_plate, make, model, model_yr, acadyr)
    #do_sql(insertVehicleSQL)
    getVehicleSQL = ("SELECT DISTINCT dbinfo('sqlca.sqlerrd1') AS veh_no FROM veh_rec")
    #veh_results = do_sql(getVehicleSQL).fetchone()
    #return veh_results.veh_no
    return insertVehicleSQL

def updateVehicle(veh_no, license, st_plate, make, model, model_yr, active_date, inactive_date):
    updateVehicleSQL = (
        " UPDATE veh_rec"
        " SET license       =   '%s',"
        "   st_plate        =   '%s',"
        "   make            =   '%s',"
        "   model           =   '%s',"
        "   model_yr        =   %s,"
        "   active_date     =   '%s',"
        "   inactive_date   =   '%s'"
        " WHERE"
        "   veh_no      =   %s"
    ) % (license, st_plate, make, model, model_yr, active_date, inactive_date, veh_no)
    #do_sql(updateVehicleSQL)
    #return veh_no
    return updateVehicleSQL

def reserveSpot(lot):
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
        "   lotcode =   '%s'"
        " GROUP BY lotcode"
    ) % (lot)
    getNext = do_sql(getNextSQL).fetchone()
    reserveSpotSQL = (
        " UPDATE prkglot_rec"
        " SET lot_stat  =   'A'"
        " WHERE"
        "   lot_no      =   %s"
    ) % (getNext.lot_no)
    #do_sql(reserveSpotSQL)
    #return getNext.lot_no
    return ("%s<br /><br />%s") % (getNextSQL, reserveSpotSQL)

def assignPermit(id, veh_no, nextSpot, acadYear):
    insertPermitSQL = (
        " INSERT INTO prkgpermt_rec"
        "   (lotcode, lotloctn, permit_code, acadyr, permt_id, veh_no, permt_stat, active_date, permtcmmnt)"
        " VALUES ('%s', '%s', '%s', '%s', %s, %s, '%s', '%s', '%s')"
    ) % (nextSpot.lotcode, nextSpot.lotloctn, '', acadYear, id, veh_no, '', TODAY, '')
    #do_sql(insertPermitSQL)

def expireVehicle(veh_no):
    vehicleExpireSQL = (
        " UPDATE veh_rec"
        " SET inactive_date = TODAY"
        " WHERE veh_no = %s"
    ) % (veh_no)
    #do_sql(vehicleExpireSQL)
    return veh_no

def ajaxCarMakes(request, year):
    #Retrieve the list of car makes for a specific year
    makes = getCarMakes(year)
    #Create string of makes delimited by a ","
    tmp = ','.join([make.make_code for make in makes])
    return HttpResponse(simplejson.dumps(tmp), content_type="application/json")

def ajaxCarModels(request, year, make):
    #Retrieve the list of models given the year and make of the car
    models = getCarModels(year, make)
    #Create string of models delimited by a ","
    tmp = ','.join([model.model_code for model in models])
    return HttpResponse(simplejson.dumps(tmp), content_type="application/json")

def ajaxStickers(request, lotcode, acadYear):
    stickers = getStickers(lotcode, acadYear)
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
