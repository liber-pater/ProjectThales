
import datetime
from dateutil.parser import parse
import MySQLdb as mdb
import urllib2
import warnings

# Obtain a database connection to the MySQL instance
db_host = '127.0.0.1'
db_port = 3306
db_user = 'root'
db_pass = ''
db_name = 'security_master'
con = mdb.connect(host=db_host, port=db_port, user=db_user, passwd=db_pass, db=db_name)
failed_tickers = []
warnings.filterwarnings('ignore', category = mdb.Warning)

def obtain_list_of_db_tickers():
	"""Obtains a list of the ticker symbols in the database that have some data."""
	with con: 
		cur = con.cursor()
		# get only symbols with some data
		cur.execute("SELECT id, ticker from symbol where id in(select symbol_id from daily_price)")
		data = cur.fetchall()
		return [(d[0], d[1]) for d in data]

def check_date(ticker):
	"""get get most recent price data available"""

	query = "SELECT max(dp.price_date) as end, min(dp.price_date) as start FROM symbol AS sym INNER JOIN daily_price AS dp ON dp.symbol_id = sym.id WHERE sym.ticker = '%s'" % ticker
	with con: 
		cur = con.cursor()
		cur.execute(query)
		data = cur.fetchall()
		
		[(d[0], d[1]) for d in data]
		stop_date =  d[0].date()
		start_date = d[1].date()

	return stop_date, start_date

def get_daily_historic_data_yahoo(ticker,
					  start_date=(1999,12,31),
					  end_date=datetime.date.today().timetuple()[0:3]):
	"""Obtains data from Yahoo Finance returns and a list of tuples.

	ticker: Yahoo Finance ticker symbol, e.g. "GOOG" for Google, Inc.
	start_date: Start date in (YYYY, M, D) format
	end_date: End date in (YYYY, M, D) format"""

	# Construct the Yahoo URL with the correct integer query parameters
	# for start and end dates. Note that some parameters are zero-based!
	yahoo_url = "http://ichart.finance.yahoo.com/table.csv?s=%s&a=%s&b=%s&c=%s&d=%s&e=%s&f=%s" % \
		(ticker, start_date[1] - 1, start_date[2], start_date[0], end_date[1] - 1, end_date[2], end_date[0])
	
	# Try connecting to Yahoo Finance and obtaining the data
	# On failure, print an error message.
	prices = []
	tries = 0
	while len(prices) == 0:
		if tries > 10 :
			print "\tFailed adding %s" % ticker
			failed_tickers.append(ticker)
			break
		else:
			try:
				yf_data = urllib2.urlopen(yahoo_url).readlines()[1:] # Ignore the header
				for y in yf_data:
					p = y.strip().split(',')
					prices.append( (datetime.datetime.strptime(p[0], '%Y-%m-%d'),
						p[1], p[2], p[3], p[4], p[5], p[6]) )
				if len(prices) == 0: # if there is no new data
					print("\tNo data!: %s" % len(prices))
					break
				print("\tdata points: %s" % len(prices))
			except Exception, e:
				tries += 1
				print(e)
				print "\tTry %d on  %s" % (tries, yahoo_url)
				pass
	return prices

def insert_daily_data_into_db(data_vendor_id, symbol_id, daily_data):
	"""Takes a list of tuples of daily data and adds it to the
	MySQL database. Appends the vendor ID and symbol ID to the data.

	daily_data: List of tuples of the OHLC data (with 
	adj_close and volume)"""

	# Create the time now
	now = datetime.datetime.utcnow()

	# Amend the data to include the vendor ID and symbol ID
	daily_data = [(data_vendor_id, symbol_id, d[0], now, now,
	d[1], d[2], d[3], d[4], d[5], d[6]) for d in daily_data]

	# Create the insert strings
	column_str = """data_vendor_id, symbol_id, price_date, created_date, 
		  last_updated_date, open_price, high_price, low_price, 
		  close_price, volume, adj_close_price"""
	insert_str = ("%s, " * 11)[:-2]
	final_str = "INSERT INTO daily_price (%s) VALUES (%s)" % (column_str, insert_str)

	# Using the MySQL connection, carry out an INSERT INTO for every symbol	
	try:
		with con: 
			cur = con.cursor()
			cur.executemany(final_str, daily_data)
	except mdb.Warning, e:
		print("\t%s"%e)
	except Exception, e:
		print("\tfailed to add symbol_id %s" % symbol_id)
		pass

if __name__ == "__main__":
	# Loop over the tickers and insert the daily historical
	# data into the database
	tickers = obtain_list_of_db_tickers()
	# warnings.filterwarnings('error', category=mdb.Warning)
	print "%d to insert" % len(tickers)
	i = 0
	start_date=(1999,12,31)
	end_date=datetime.date.today()

	for t in tickers:
		# existing start and end dates
		stop_date,start_date = check_date(t[1])

		# if data isnt up to date
		if  stop_date < end_date :
			
			# add one to not duplicate data
			stop_date +=  datetime.timedelta(days=1)
			print "%d %s\t Adding: %s : %s" % (i,t[1], stop_date, end_date)
			
			#split it to conform with format of def
			stop_date = (stop_date.year,stop_date.month,stop_date.day)

			# get data and insert it
			yf_data = get_daily_historic_data_yahoo(t[1],stop_date)
			insert_daily_data_into_db('1', t[0], yf_data)
			i+=1
	print "Total tickers updated: %d" % i



