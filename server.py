from flask import Flask, render_template
import pandas as pd
import requests
import json
import feedparser

app = Flask(__name__)

#Home route
@app.route("/")
def home():
    return 'You are at the Home Page. Choose /shelters for shelter list, /alerts for live feed or /archive for Hurricane Katrina info. '

# Shelters route
@app.route("/shelters", methods=['GET'])
def index():
  open_shelters = requests.get('https://gis.fema.gov/arcgis/rest/services/NSS/OpenShelters/MapServer/0/query?where=1%3D1&outFields=*&outSR=4326&f=json')
  open_shelters_info = open_shelters.json()
  return open_shelters_info

# Archive route
@app.route("/archive", methods=['GET'])
def archive_feed():
    feedpath = "./archive_feed"
    
    filename = 'stormdata.txt'

    
    NewsFeed = feedparser.parse(feedpath)
    N = len(NewsFeed['entries'])
    titles = [e['title'] for e in NewsFeed['entries']]

    # check for "Public Advisory" in titles list. If it's not there; there is no current storm in the feed
    currentadv = [n for n in range(N) if 'Public Advisory' in titles[n]]

    # case where no current storm:
    if len(currentadv)==0:
        current = ''
        currentinfo = {
                'datetime':           'NO CURRENT STORM',
                'current_latitude':   'NO CURRENT STORM',
                'current_longitude':  'NO CURRENT STORM',
                'winds_mph':          'NO CURRENT STORM',
                'storm_category':     'NO CURRENT STORM',
                'pressure_mbar':      'NO CURRENT STORM',
                'radius':             'NO CURRENT STORM',
                'time_of_landfall':   'NO CURRENT STORM',
                'movement_direction': 'NO CURRENT STORM',
                'movement_speed':     'NO CURRENT STORM',
                'watch_updates':      'NO CURRENT STORM',
                'warning_updates':    'NO CURRENT STORM',
                'alerts_summary':     'NO CURRENT STORM'
            }

    # case of one or more storms:
    else:
        # loop over whatever storms there are -- usually just one:
        n = 0
        # pull off the advisory text, do preliminary cleaning:
        currentadv = currentadv[n]
        current = ''.join(NewsFeed['entries'][currentadv].summary.split('\n'))
        current = current.replace('--','')
        current = ''.join([c.upper() for c in current])
            
        # find the center pressure (mbar) and the wind speed text:
        pressure = current.split('PRESSURE...')[1].split('...')[0]
        pressureval = int(pressure.split(' ')[0])
        winds = current.split('WINDS...')[1].split('...')[0]
            
        # convert the wind speed text to numberic value, and then use that to define the storm category
        # Using the Saffir-Simpson scale for hurricanes. Reference here : https://www.nhc.noaa.gov/aboutsshws.php
        windval = int(winds.split(' ')[0])
        if windval>=157:   category = 'Cat 5 Hurricane' 
        elif windval>=130: category = 'Cat 4 Hurricane'
        elif windval>=111: category = 'Cat 3 Hurricane'
        elif windval>=96:  category = 'Cat 2 Hurricane'
        elif windval>=74:  category = 'Cat 1 Hurricane'
        elif windval>=39:  category = 'Tropical Storm'
        else:              category = 'Subtropical'

        # radius is pulled from a different section, "description" instead of "summary":    
        chk0 = ''.join(NewsFeed['entries'][currentadv]['description'].split('\n'))
        chk0 = ''.join([c.upper() for c in chk0])
        # if there is no info for the storm radius, use 300 mi as the default, as that is a typical value
        # https://www.weather.gov/source/zhu/ZHU_Training_Page/tropical_stuff/hurricane_anatomy/hurricane_anatomy.html
        defaultradius = 300
        # text can vary - looking for either "radius", "radii", "diameter" or "extend outward" 
        # Not just "extend" because that might mean time instead of space
        if 'RADI' in chk0:
            wrd = 'RADI'
        elif 'DIAMETER' in chk0:
            wrd = 'DIAMETER'
        elif 'EXTEND OUTWARD' in chk0:
            wrd = 'EXTEND OUTWARD'
        else: 
            wrd = ''
        if wrd != '':
            chk = chk0.split(wrd)[1].split(' ')
            nums = [n for n in range(len(chk)) if chk[n].isdigit()]
            if len(nums)>0: 
                firstnum = nums[0]
                radius = int(chk[firstnum])
                # divide by 2 if diameter was provided instead of radius:
                if wrd == 'DIAMETER': radius = radius/2
                # convert to miles if radius was given in km instead:
                unit = chk[firstnum+1]
                if unit[0:2]=='KM': radius *= 0.621371
            else:
                radius = defaultradius
        else:
            radius = defaultradius

        # projected time of landfall is a text string in the "Forecast Discussion" section:
        forecastdis = [n for n in range(N) if 'Forecast Discussion' in titles[n]]
        if len(forecastdis)>0:
            forecastdis = forecastdis[0]
            chk = ''.join(NewsFeed['entries'][forecastdis]['summary'].split('\n')).split('. ')
            # need noth "LANDFALL" and an indication of time, or else it might be a statement of coastal erosion expected within 
            # a certain distance of landfall
            # if there is no such string, save a default statement
            timingtext = [c for c in chk if ('LANDFALL' in c) and (('MORNING' in c) or ('AFTERNOON' in c) or ('EVENING' in c) or ('NIGHT' in c))]
            if len(timingtext)>0:
                timingtext = timingtext[0]
            else:
                timingtext = 'TIME OF LANDFALL UNKNOWN'
        else:
            timingtext = 'TIME OF LANDFALL UNKNOWN'
                
        # get the current location of the storm center:
        location = current.split('LOCATION...')[1].split('ABOUT')[0].split(' ')
        latitude = float(location[0].replace(' ','').replace('N',''))
        longitude = -1*float(location[1].replace(' ','').replace('W',''))

        # get the time of the advisory:
        issuetime = current.split('ISSUED AT ')[1].split(' <PRE')[0]

        # get the projected path direction and speed (does NOT include the cone of uncertainty) :
        movement = current.split('MOVEMENT...')[1].split('...')[0].split(' OR ')[1].split(' AT ')
        pathdirection = int(movement[0].split(' ')[0])
        pathspeed = int(movement[1].split(' ')[0])

        warningtext = current.split('CHANGES WITH THIS ADVISORY')[1].split(' DISCUSSION')[0]
        warningtext = warningtext.split('SUMMARY OF')
        summarytext = warningtext[1]
        warningtext = warningtext[0]
        warningtext = warningtext.replace('ST.','ST')
        warningtext = warningtext.replace('WARNING',' WARNING ')
        warningtext = warningtext.replace('WATCH',' WATCH ')
        warningtext = warningtext.replace('U.S.','US')
        warningtext = warningtext.replace('...','-')
        alerts = warningtext.split('.')
        summarytext = summarytext.replace(' A TROPICAL STORM WARNING MEANS THAT TROPICAL STORM CONDITIONS ARE EXPECTED SOMEWHERE WITHIN THE WARNING AREA WITHIN 36 HOURS.','')
        summarytext = summarytext.replace(' A TROPICAL STORM WATCH MEANS THAT TROPICAL STORM CONDITIONS ARE POSSIBLE WITHIN THE WATCH AREA-GENERALLY WITHIN 48 HOURS.','')
        summarytext = summarytext.replace(' A HURRICANE WARNING MEANS THAT HURRICANE CONDITIONS ARE EXPECTED SOMEWHERE WITHIN THE WARNING AREA WITHIN 36 HOURS.','')
        summarytext = summarytext.replace(' A HURRICANE WATCH MEANS THAT HURRICANE CONDITIONS ARE POSSIBLE WITHIN THE WATCH AREA-GENERALLY WITHIN 48 HOURS.','')
        summarytext = summarytext.replace(' FOR STORM INFORMATION SPECIFIC TO YOUR AREA-INCLUDING POSSIBLE INLAND WATCHES AND WARNINGS-PLEASE MONITOR PRODUCTS ISSUED BY YOUR LOCAL NATIONAL WEATHER SERVICE FORECAST OFFICE.','')
        watchtext   = ''.join([c for c in alerts if ('WATCH' in c)])
        warningtext = ''.join([c for c in alerts if ('WARNING' in c)])
        if (watchtext=='') and (warningtext==''): summarytext = 'NO CHANGES: ' + summarytext

        # compile data:
        currentinfo = {
            'datetime':           issuetime,
            'current_latitude':   latitude,
            'current_longitude':  longitude,
            'winds_mph':          windval,
            'storm_category':     category,
            'pressure_mbar':      pressureval,
            'radius':             radius,
            'time_of_landfall':   timingtext,
            'movement_direction_cw_from_N': pathdirection,
            'movement_speed_mph':     pathspeed,
            'watch_updates':      watchtext,
            'warning_updates':    warningtext,
            'alerts_summary':     summarytext
        }

    # save data:
    # currentinfo.to_csv('./'+filename, index=False)
    with open('./'+filename,'w') as outfile:
        json.dump(currentinfo,outfile)
    return currentinfo

# Live feed route
@app.route("/alerts", methods=['GET'])
def alert():

    feedpath = "https://www.nhc.noaa.gov/index-at.xml"
    
    filename = 'stormdata.txt'

    
    NewsFeed = feedparser.parse(feedpath)
    N = len(NewsFeed['entries'])
    titles = [e['title'] for e in NewsFeed['entries']]

    # check for "Public Advisory" in titles list. If it's not there; there is no current storm in the feed
    currentadv = [n for n in range(N) if 'Public Advisory' in titles[n]]

    # case where no current storm:
    if len(currentadv)==0:
        current = ''
        currentinfo = {
                'datetime':           'NO CURRENT STORM',
                'current_latitude':   'NO CURRENT STORM',
                'current_longitude':  'NO CURRENT STORM',
                'winds_mph':          'NO CURRENT STORM',
                'storm_category':     'NO CURRENT STORM',
                'pressure_mbar':      'NO CURRENT STORM',
                'radius':             'NO CURRENT STORM',
                'time_of_landfall':   'NO CURRENT STORM',
                'movement_direction': 'NO CURRENT STORM',
                'movement_speed':     'NO CURRENT STORM',
                'watch_updates':      'NO CURRENT STORM',
                'warning_updates':    'NO CURRENT STORM',
                'alerts_summary':     'NO CURRENT STORM'
            }

    # case of one or more storms:
    else:
        # loop over whatever storms there are -- usually just one:
        n = 0
        # pull off the advisory text, do preliminary cleaning:
        currentadv = currentadv[n]
        current = ''.join(NewsFeed['entries'][currentadv].summary.split('\n'))
        current = current.replace('--','')
        current = ''.join([c.upper() for c in current])
            
        # find the center pressure (mbar) and the wind speed text:
        pressure = current.split('PRESSURE...')[1].split('...')[0]
        pressureval = int(pressure.split(' ')[0])
        winds = current.split('WINDS...')[1].split('...')[0]
            
        # convert the wind speed text to numberic value, and then use that to define the storm category
        # Using the Saffir-Simpson scale for hurricanes. Reference here : https://www.nhc.noaa.gov/aboutsshws.php
        windval = int(winds.split(' ')[0])
        if windval>=157:   category = 'Cat 5 Hurricane' 
        elif windval>=130: category = 'Cat 4 Hurricane'
        elif windval>=111: category = 'Cat 3 Hurricane'
        elif windval>=96:  category = 'Cat 2 Hurricane'
        elif windval>=74:  category = 'Cat 1 Hurricane'
        elif windval>=39:  category = 'Tropical Storm'
        else:              category = 'Subtropical'

        # radius is pulled from a different section, "description" instead of "summary":    
        chk0 = ''.join(NewsFeed['entries'][currentadv]['description'].split('\n'))
        chk0 = ''.join([c.upper() for c in chk0])
        # if there is no info for the storm radius, use 300 mi as the default, as that is a typical value
        # https://www.weather.gov/source/zhu/ZHU_Training_Page/tropical_stuff/hurricane_anatomy/hurricane_anatomy.html
        defaultradius = 300
        # text can vary - looking for either "radius", "radii", "diameter" or "extend outward" 
        # Not just "extend" because that might mean time instead of space
        if 'RADI' in chk0:
            wrd = 'RADI'
        elif 'DIAMETER' in chk0:
            wrd = 'DIAMETER'
        elif 'EXTEND OUTWARD' in chk0:
            wrd = 'EXTEND OUTWARD'
        else: 
            wrd = ''
        if wrd != '':
            chk = chk0.split(wrd)[1].split(' ')
            nums = [n for n in range(len(chk)) if chk[n].isdigit()]
            if len(nums)>0: 
                firstnum = nums[0]
                radius = int(chk[firstnum])
                # divide by 2 if diameter was provided instead of radius:
                if wrd == 'DIAMETER': radius = radius/2
                # convert to miles if radius was given in km instead:
                unit = chk[firstnum+1]
                if unit[0:2]=='KM': radius *= 0.621371
            else:
                radius = defaultradius
        else:
            radius = defaultradius

        # projected time of landfall is a text string in the "Forecast Discussion" section:
        forecastdis = [n for n in range(N) if 'Forecast Discussion' in titles[n]]
        if len(forecastdis)>0:
            forecastdis = forecastdis[0]
            chk = ''.join(NewsFeed['entries'][forecastdis]['summary'].split('\n')).split('. ')
            # need noth "LANDFALL" and an indication of time, or else it might be a statement of coastal erosion expected within 
            # a certain distance of landfall
            # if there is no such string, save a default statement
            timingtext = [c for c in chk if ('LANDFALL' in c) and (('MORNING' in c) or ('AFTERNOON' in c) or ('EVENING' in c) or ('NIGHT' in c))]
            if len(timingtext)>0:
                timingtext = timingtext[0]
            else:
                timingtext = 'TIME OF LANDFALL UNKNOWN'
        else:
            timingtext = 'TIME OF LANDFALL UNKNOWN'
                
        # get the current location of the storm center:
        location = current.split('LOCATION...')[1].split('ABOUT')[0].split(' ')
        latitude = float(location[0].replace(' ','').replace('N',''))
        longitude = -1*float(location[1].replace(' ','').replace('W',''))

        # get the time of the advisory:
        issuetime = current.split('ISSUED AT ')[1].split(' <PRE')[0]

        # get the projected path direction and speed (does NOT include the cone of uncertainty) :
        movement = current.split('MOVEMENT...')[1].split('...')[0].split(' OR ')[1].split(' AT ')
        pathdirection = int(movement[0].split(' ')[0])
        pathspeed = int(movement[1].split(' ')[0])

        warningtext = current.split('CHANGES WITH THIS ADVISORY')[1].split(' DISCUSSION')[0]
        warningtext = warningtext.split('SUMMARY OF')
        summarytext = warningtext[1]
        warningtext = warningtext[0]
        warningtext = warningtext.replace('ST.','ST')
        warningtext = warningtext.replace('WARNING',' WARNING ')
        warningtext = warningtext.replace('WATCH',' WATCH ')
        warningtext = warningtext.replace('U.S.','US')
        warningtext = warningtext.replace('...','-')
        alerts = warningtext.split('.')
        summarytext = summarytext.replace(' A TROPICAL STORM WARNING MEANS THAT TROPICAL STORM CONDITIONS ARE EXPECTED SOMEWHERE WITHIN THE WARNING AREA WITHIN 36 HOURS.','')
        summarytext = summarytext.replace(' A TROPICAL STORM WATCH MEANS THAT TROPICAL STORM CONDITIONS ARE POSSIBLE WITHIN THE WATCH AREA-GENERALLY WITHIN 48 HOURS.','')
        summarytext = summarytext.replace(' A HURRICANE WARNING MEANS THAT HURRICANE CONDITIONS ARE EXPECTED SOMEWHERE WITHIN THE WARNING AREA WITHIN 36 HOURS.','')
        summarytext = summarytext.replace(' A HURRICANE WATCH MEANS THAT HURRICANE CONDITIONS ARE POSSIBLE WITHIN THE WATCH AREA-GENERALLY WITHIN 48 HOURS.','')
        summarytext = summarytext.replace(' FOR STORM INFORMATION SPECIFIC TO YOUR AREA-INCLUDING POSSIBLE INLAND WATCHES AND WARNINGS-PLEASE MONITOR PRODUCTS ISSUED BY YOUR LOCAL NATIONAL WEATHER SERVICE FORECAST OFFICE.','')
        watchtext   = ''.join([c for c in alerts if ('WATCH' in c)])
        warningtext = ''.join([c for c in alerts if ('WARNING' in c)])
        if (watchtext=='') and (warningtext==''): summarytext = 'NO CHANGES: ' + summarytext

        # compile data:
        currentinfo = {
            'datetime':           issuetime,
            'current_latitude':   latitude,
            'current_longitude':  longitude,
            'winds_mph':          windval,
            'storm_category':     category,
            'pressure_mbar':      pressureval,
            'radius':             radius,
            'time_of_landfall':   timingtext,
            'movement_direction_cw_from_N': pathdirection,
            'movement_speed_mph':     pathspeed,
            'watch_updates':      watchtext,
            'warning_updates':    warningtext,
            'alerts_summary':     summarytext
        }

    # save data:
    # currentinfo.to_csv('./'+filename, index=False)
    with open('./'+filename,'w') as outfile:
        json.dump(currentinfo,outfile)


    

    return currentinfo



  

if __name__ == "__main__":
    app.run(debug=True)