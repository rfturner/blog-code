import sqlite3 as sql
import numpy as np
import datetime as dt
import pandas as pd
from sklearn.linear_model import LinearRegression

def main( **kwargs ):

    conn = sql.connect( kwargs[ 'dbPath' ] )
    cursor = conn.cursor()

    startDate = kwargs[ 'startDate' ]
    nQuarters = kwargs[ 'nQuarters' ]

    dates = []
    currentDate = startDate
    for quarter in range( nQuarters + 1):
        dates.append( currentDate.isoformat() )
        currentDate += dt.timedelta( 90 ) # advance by 90 days

    # doesn't exactly align with quarterly start dates,
    # but close enough for this estimate


    # get dealer id's
    query = """SELECT dealer_id FROM orders GROUP BY dealer_id;"""
    cursor.execute( query )
    dealerIDs = [ x[ 0 ] for x in cursor.fetchall() ]

    # create data frame to hold results
    salesFrame = pd.DataFrame( np.nan, index = range( nQuarters ), columns = dealerIDs )

    query = """SELECT dealer_id, SUM( customer_total + warranty_total + internal_total )
                      FROM orders WHERE ro_close_date BETWEEN ? AND ?
                      GROUP BY dealer_id;"""

    # fill data frame with results
    for qStart in range( len( dates ) - 1 ):
        qEnd = qStart + 1
        cursor.execute( query, ( dates[ qStart ], dates[ qEnd ] ) )
        res = cursor.fetchall()
        for line in res:
            salesFrame.loc[ qStart, line[ 0 ] ] = line[ 1 ]

    # linear fit to quarterly sales to determine quarterly growth

    growthFactor = {}
    for dealer in salesFrame.columns:
        sales = salesFrame.loc[ :, dealer ].values
        quarters = np.arange( nQuarters )

        # filter nan
        xTrain = quarters[ np.isfinite( sales ), np.newaxis ]
        yTrain = sales[ np.isfinite( sales ) ] / 1000.

        if yTrain.shape[ 0 ] >= kwargs[ 'minThresholdforFit' ]:
            clf = LinearRegression( fit_intercept = True )
            clf.fit( xTrain, yTrain )
            # growth = slope of line (thousands/quarter)
            growthFactor[ dealer ] = clf.coef_[ 0 ]
        else:
            # fill with mean growth
            print 'not enough results for dealer ', dealer
            growthFactor[ dealer ] = np.mean( growthFactor.values() )

    # insert calculated growth into SQL DB
    statement = """DROP TABLE growth"""
    cursor.execute( statement)
    statement = """CREATE TABLE growth
                      (dealer_id integer, quarterly_growth float); """
    cursor.execute( statement )
    
    ins = []
    for dealer in growthFactor:
        ins.append( ( dealer, growthFactor[ dealer ] ) )

    statement = """INSERT INTO growth VALUES (?,?);"""
    cursor.executemany( statement, ins )
    conn.commit()

if __name__ == '__main__':
    kwargs = { 'dbPath': '/Users/jardel/SR/subset.sql',
               'startDate': dt.date( 2010, 06, 30 ),
               'nQuarters': 7,
               'minThresholdforFit': 3
               }
    main( **kwargs )
        
