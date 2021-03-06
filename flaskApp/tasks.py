from flaskApp import celery
from flask import jsonify
import dcs.load
import dcs.view
import dcs.analyze
import dcs.clean
import os
import requests
import pandas as pd
import numpy as np
import json
import datetime
import traceback

# Returns a sessionID (str) on successful conversion, and None on fail
@celery.task()
def userUploadedCSVToDataFrame(uploadID, initialSkip, sampleSize, seed, headerIncluded):
	toReturn = None
	path = 'flaskApp/temp/' + uploadID + '.csv'
	if uploadID and os.path.isfile(path):
		data = dcs.load.CSVtoDataFrame('flaskApp/temp/' + uploadID + '.csv', initialSkip=initialSkip, sampleSize=sampleSize, seed=seed, headerIncluded=headerIncluded)
		os.remove(path)
		if data is not None and saveToCache(data, uploadID):
			toReturn = uploadID
	return toReturn

# Returns a sessionID (str) on successful conversion, and None on fail
@celery.task()
def userUploadedJSONToDataFrame(uploadID, initialSkip, sampleSize, seed):
	toReturn = None
	path = 'flaskApp/temp/' + uploadID + '.json'
	if uploadID and os.path.isfile(path):
		data = dcs.load.JSONtoDataFrame('flaskApp/temp/' + uploadID + '.json', sampleSize=sampleSize, seed=seed)
		os.remove(path)
		if data is not None and saveToCache(data, uploadID):
			toReturn = uploadID
	return toReturn

# Returns a sessionID (str) on successful conversion, and None on fail
@celery.task()
def userUploadedXLSXToDataFrame(uploadID, initialSkip, sampleSize, seed, headerIncluded):
	toReturn = None
	path = 'flaskApp/temp/' + uploadID + '.xlsx'
	if uploadID and os.path.isfile(path):
		data = dcs.load.XLSXtoDataFrame('flaskApp/temp/' + uploadID + '.xlsx', initialSkip=initialSkip, sampleSize=sampleSize, seed=seed, headerIncluded=headerIncluded)
		os.remove(path)
		if data is not None and saveToCache(data, uploadID):
			toReturn = uploadID
	return toReturn

# Returns a sessionID (str) on successful conversion, and None on fail
@celery.task()
def userUploadedXLSToDataFrame(uploadID, initialSkip, sampleSize, seed, headerIncluded):
	toReturn = None
	path = 'flaskApp/temp/' + uploadID + '.xls'
	if uploadID and os.path.isfile(path):
		data = dcs.load.XLSXtoDataFrame('flaskApp/temp/' + uploadID + '.xls', initialSkip=initialSkip, sampleSize=sampleSize, seed=seed, headerIncluded=headerIncluded)
		os.remove(path)
		if data is not None and saveToCache(data, uploadID):
			toReturn = uploadID
	return toReturn

# Returns True if backup for undo is available, False otherwise
def undoAvailable(sessionID):
	return type(loadDataFrameFromCache(sessionID, "undo")) is pd.DataFrame

# Returns a pandas.DataFrame on successful loading, and None on fail
@celery.task()
def loadDataFrameFromCache(sessionID, key="original"):
	if isinstance(sessionID, basestring) and len(sessionID) == 30:
		try:
			data = pd.read_hdf("flaskApp/cache/" + sessionID + ".h5", key)
			if type(data) is pd.DataFrame:
				return data
		except:
			pass
	return None

# Returns a csv object of a datarame on success, and None on fail
@celery.task()
def DataFrameToCSV(sessionID):
	df = loadDataFrameFromCache(sessionID)
	if type(df) is pd.DataFrame:
		return df.to_csv(None, index=False, force_ascii=False)
	else:
		return None

# Returns JSON representation of a dataframe on success, and None on fail
@celery.task()
def DFtoJSON(sessionID):
	df = loadDataFrameFromCache(sessionID)
	if type(df) is pd.DataFrame:
		return df.to_json(orient="records", date_format="iso", force_ascii=True)
	else:
		return None

# Ensures column names in dataframe are unique, renaming columns in-place
def uniquefyDataFrameColumnNames(df):
	frequencies = {}
	newNames = []
	for index, name in enumerate(reversed(df.columns)):
		if frequencies.get(name, 0) > 0:
			newName = "%s.%d" % (name, frequencies[name])
			incrementer = 0
			while newName in df.columns:
				incrementer += 1
				newName = "%s.%d" % (name, frequencies[name] + incrementer)
			newNames.append(newName)
		else:
			newNames.append(name)

		frequencies[name] = frequencies.get(name, 0) + 1

	df.columns = reversed(newNames)

# Returns True on successful save, and False on fail
@celery.task()
def saveToCache(df, sessionID):
	if isinstance(sessionID, basestring) and len(sessionID) == 30:
		try:
			uniquefyDataFrameColumnNames(df) # hdf fixed format does not support duplicate column names

			path = "flaskApp/cache/" + sessionID + ".h5"
			oldDF = loadDataFrameFromCache(sessionID)
			if type(oldDF) is pd.DataFrame:
				# save one undo
				oldDF.to_hdf(path, "undo", mode="w", format="fixed")

			df.to_hdf(path, "original", mode="a", format="fixed")
			return True
		except Exception as e:
			print("failed to save hdf ", e)
	return False

# POSTs JSON result to Flask app on /celeryTaskCompleted/ endpoint
@celery.task()
def undo(sessionID, requestID):
	toReturn = {'success' : False, 'requestID': requestID, 'sessionID': sessionID, 'operation': "undo"}
	backup = loadDataFrameFromCache(sessionID, "undo")

	if type(backup) is pd.DataFrame:
		saveToCache(backup, sessionID)
		toReturn['changed'] = True
		toReturn['success'] = True
	else:
		toReturn['error'] = "IllegalOperation"
		toReturn['errorDescription'] = "The undo operation is currently not available on this dataframe. "

	try:
		requests.post("http://localhost:5000/celeryTaskCompleted/", json=toReturn, timeout=0.001)
	except:
		pass

# POSTs JSON result to Flask app on /celeryTaskCompleted/ endpoint
@celery.task()
def renameColumn(sessionID, requestID, column, newName):
	toReturn = {'success' : False, 'requestID': requestID, 'sessionID': sessionID, 'operation': "renameColumn"}
	df = loadDataFrameFromCache(sessionID)

	try:
		dcs.load.renameColumn(df, column, newName)
		saveToCache(df, sessionID)
		toReturn['changed'] = True
		toReturn['success'] = True
	except Exception as e:
		toReturn['error'] = str(e)
		toReturn['errorDescription'] = traceback.format_exc()

	try:
		requests.post("http://localhost:5000/celeryTaskCompleted/", json=toReturn, timeout=0.001)
	except:
		pass

# POSTs JSON result to Flask app on /celeryTaskCompleted/ endpoint
@celery.task()
def newCellValue(sessionID, requestID, columnIndex, rowIndex, newValue):
	toReturn = {'success' : False, 'requestID': requestID, 'sessionID': sessionID, 'operation': "newCellValue"}
	df = loadDataFrameFromCache(sessionID)

	try:
		dcs.load.newCellValue(df, columnIndex, rowIndex, newValue)
		saveToCache(df, sessionID)
		toReturn['changed'] = True
		toReturn['success'] = True
	except Exception as e:
		toReturn['error'] = str(e)
		toReturn['errorDescription'] = traceback.format_exc()

	try:
		requests.post("http://localhost:5000/celeryTaskCompleted/", json=toReturn, timeout=0.001)
	except:
		pass

# POSTs JSON result to Flask app on /celeryTaskCompleted/ endpoint
@celery.task()
def changeColumnDataType(sessionID, requestID, column, newDataType, dateFormat=None):
	toReturn = {'success' : False, 'requestID': requestID, 'sessionID': sessionID, 'operation': "changeColumnDataType"}
	df = loadDataFrameFromCache(sessionID)

	try:
		dcs.load.changeColumnDataType(df, column, newDataType, dateFormat=dateFormat)
		saveToCache(df, sessionID)
		toReturn['changed'] = True
		toReturn['success'] = True
	except Exception as e:
		toReturn['error'] = str(e)
		toReturn['errorDescription'] = traceback.format_exc()

	try:
		requests.post("http://localhost:5000/celeryTaskCompleted/", json=toReturn, timeout=0.001)
	except:
		pass

# POSTs JSON result to Flask app on /celeryTaskCompleted/ endpoint
@celery.task()
def deleteRows(sessionID, requestID, rowIndices):
	toReturn = {'success' : False, 'requestID': requestID, 'sessionID': sessionID, 'operation': "deleteRows"}
	df = loadDataFrameFromCache(sessionID)

	try:
		dcs.load.removeRows(df, rowIndices)
		saveToCache(df, sessionID)
		toReturn['changed'] = True
		toReturn['success'] = True
	except Exception as e:
		toReturn['error'] = str(e)
		toReturn['errorDescription'] = traceback.format_exc()

	try:
		requests.post("http://localhost:5000/celeryTaskCompleted/", json=toReturn, timeout=0.001)
	except:
		pass

# POSTs JSON result to Flask app on /celeryTaskCompleted/ endpoint
@celery.task()
def deleteColumns(sessionID, requestID, columnIndices):
	toReturn = {'success' : False, 'requestID': requestID, 'sessionID': sessionID, 'operation': "deleteColumns"}
	df = loadDataFrameFromCache(sessionID)

	try:
		dcs.load.removeColumns(df, columnIndices)
		saveToCache(df, sessionID)
		toReturn['changed'] = True
		toReturn['success'] = True
	except Exception as e:
		toReturn['error'] = str(e)
		toReturn['errorDescription'] = traceback.format_exc()

	try:
		requests.post("http://localhost:5000/celeryTaskCompleted/", json=toReturn, timeout=0.001)
	except:
		pass

# POSTs JSON result to Flask app on /celeryTaskCompleted/ endpoint
@celery.task()
def emptyStringToNan(sessionID, requestID, columnIndex):
	toReturn = {'success' : False, 'requestID': requestID, 'sessionID': sessionID, 'operation': "emptyStringToNan"}
	df = loadDataFrameFromCache(sessionID)

	try:
		dcs.load.emptyStringToNan(df, columnIndex)
		saveToCache(df, sessionID)
		toReturn['changed'] = True
		toReturn['success'] = True
	except Exception as e:
		toReturn['error'] = str(e)
		toReturn['errorDescription'] = traceback.format_exc()

	try:
		requests.post("http://localhost:5000/celeryTaskCompleted/", json=toReturn, timeout=0.001)
	except:
		pass

# POSTs JSON result to Flask app on /celeryTaskCompleted/ endpoint
@celery.task()
def fillDown(sessionID, requestID, columnFrom, columnTo, method):
	toReturn = {'success' : False, 'requestID': requestID, 'sessionID': sessionID, 'operation': "fillDown"}
	df = loadDataFrameFromCache(sessionID)
	
	try:
		dcs.clean.fillDown(df, columnFrom, columnTo, method)
		saveToCache(df, sessionID)
		toReturn['changed'] = list(range(columnFrom, columnTo + 1))
		toReturn['success'] = True
	except Exception as e:
		toReturn['error'] = str(e)
		toReturn['errorDescription'] = traceback.format_exc()

	try:
		requests.post("http://localhost:5000/celeryTaskCompleted/", json=toReturn, timeout=0.001)
	except:
		pass

# POSTs JSON result to Flask app on /celeryTaskCompleted/ endpoint
@celery.task()
def interpolate(sessionID, requestID, columnIndex, method, order):
	toReturn = {'success' : False, 'requestID': requestID, 'sessionID': sessionID, 'operation': "interpolate"}
	df = loadDataFrameFromCache(sessionID)
	
	try:
		dcs.clean.fillByInterpolation(df, columnIndex, method, order)
		saveToCache(df, sessionID)
		toReturn['changed'] = True
		toReturn['success'] = True
	except MemoryError as e:
		toReturn['error'] = "Memory Error"
		toReturn['errorDescription'] = traceback.format_exc()
	except Exception as e:
		toReturn['error'] = str(e)
		toReturn['errorDescription'] = traceback.format_exc()

	try:
		requests.post("http://localhost:5000/celeryTaskCompleted/", json=toReturn, timeout=0.001)
	except:
		pass

# POSTs JSON result to Flask app on /celeryTaskCompleted/ endpoint
@celery.task()
def fillWithCustomValue(sessionID, requestID, columnIndex, newValue):
	toReturn = {'success' : False, 'requestID': requestID, 'sessionID': sessionID, 'operation': "fillWithCustomValue"}
	df = loadDataFrameFromCache(sessionID)
	
	try:
		dcs.clean.fillWithCustomValue(df, columnIndex, newValue)
		saveToCache(df, sessionID)
		toReturn['changed'] = True
		toReturn['success'] = True
	except Exception as e:
		toReturn['error'] = str(e)
		toReturn['errorDescription'] = traceback.format_exc()

	try:
		requests.post("http://localhost:5000/celeryTaskCompleted/", json=toReturn, timeout=0.001)
	except:
		pass

# POSTs JSON result to Flask app on /celeryTaskCompleted/ endpoint
@celery.task()
def fillWithAverage(sessionID, requestID, columnIndex, metric):
	toReturn = {'success' : False, 'requestID': requestID, 'sessionID': sessionID, 'operation': "fillWithAverage"}
	df = loadDataFrameFromCache(sessionID)
	
	try:
		dcs.clean.fillWithAverage(df, columnIndex, metric)
		saveToCache(df, sessionID)
		toReturn['changed'] = True
		toReturn['success'] = True
	except Exception as e:
		toReturn['error'] = str(e)
		toReturn['errorDescription'] = traceback.format_exc()

	try:
		requests.post("http://localhost:5000/celeryTaskCompleted/", json=toReturn, timeout=0.001)
	except:
		pass

# POSTs JSON result to Flask app on /celeryTaskCompleted/ endpoint
@celery.task()
def normalize(sessionID, requestID, columnIndex, rangeFrom, rangeTo):
	toReturn = {'success' : False, 'requestID': requestID, 'sessionID': sessionID, 'operation': "normalize"}
	df = loadDataFrameFromCache(sessionID)
	
	try:
		dcs.clean.normalize(df, columnIndex, rangeFrom, rangeTo)
		saveToCache(df, sessionID)
		toReturn['changed'] = True
		toReturn['success'] = True
	except Exception as e:
		toReturn['error'] = str(e)
		toReturn['errorDescription'] = traceback.format_exc()

	try:
		requests.post("http://localhost:5000/celeryTaskCompleted/", json=toReturn, timeout=0.001)
	except:
		pass

# POSTs JSON result to Flask app on /celeryTaskCompleted/ endpoint
@celery.task()
def standardize(sessionID, requestID, columnIndex):
	toReturn = {'success' : False, 'requestID': requestID, 'sessionID': sessionID, 'operation': "standardize"}
	df = loadDataFrameFromCache(sessionID)
	
	try:
		dcs.clean.standardize(df, columnIndex)
		saveToCache(df, sessionID)
		toReturn['changed'] = True
		toReturn['success'] = True
	except Exception as e:
		toReturn['error'] = str(e)
		toReturn['errorDescription'] = traceback.format_exc()

	try:
		requests.post("http://localhost:5000/celeryTaskCompleted/", json=toReturn, timeout=0.001)
		print("standardize done")
	except:
		pass

# POSTs JSON result to Flask app on /celeryTaskCompleted/ endpoint
@celery.task()
def deleteRowsWithNA(sessionID, requestID, columnIndex):
	toReturn = {'success' : False, 'requestID': requestID, 'sessionID': sessionID, 'operation': "deleteRowsWithNA"}
	df = loadDataFrameFromCache(sessionID)

	try:
		dcs.clean.deleteRowsWithNA(df, columnIndex)
		saveToCache(df, sessionID)
		toReturn['changed'] = True
		toReturn['success'] = True
	except Exception as e:
		toReturn['error'] = str(e)
		toReturn['errorDescription'] = traceback.format_exc()

	try:
		requests.post("http://localhost:5000/celeryTaskCompleted/", json=toReturn, timeout=0.001)
	except:
		pass

# POSTs JSON result to Flask app on /celeryTaskCompleted/ endpoint
@celery.task()
def findReplace(sessionID, requestID, columnIndex, toReplace, replaceWith, matchRegex):
	toReturn = {'success' : False, 'requestID': requestID, 'sessionID': sessionID, 'operation': "findReplace"}
	df = loadDataFrameFromCache(sessionID)
	
	try:
		dcs.clean.findReplace(df, columnIndex, toReplace, replaceWith, matchRegex)
		saveToCache(df, sessionID)
		toReturn['changed'] = True
		toReturn['success'] = True
	except Exception as e:
		toReturn['error'] = str(e)
		toReturn['errorDescription'] = traceback.format_exc()

	try:
		requests.post("http://localhost:5000/celeryTaskCompleted/", json=toReturn, timeout=0.001)
	except:
		pass

# POSTs JSON result to Flask app on /celeryTaskCompleted/ endpoint
@celery.task()
def generateDummies(sessionID, requestID, columnIndex, inplace):
	toReturn = {'success' : False, 'requestID': requestID, 'sessionID': sessionID, 'operation': "generateDummies"}
	df = loadDataFrameFromCache(sessionID)
	
	try:
		dcs.clean.generateDummies(df, columnIndex, inplace)
		saveToCache(df, sessionID)
		toReturn['changed'] = True
		toReturn['success'] = True
	except Exception as e:
		toReturn['error'] = str(e)
		toReturn['errorDescription'] = traceback.format_exc()

	try:
		requests.post("http://localhost:5000/celeryTaskCompleted/", json=toReturn, timeout=0.001)
	except:
		pass

# POSTs JSON result to Flask app on /celeryTaskCompleted/ endpoint
@celery.task()
def insertDuplicateColumn(sessionID, requestID, columnIndex):
	toReturn = {'success' : False, 'requestID': requestID, 'sessionID': sessionID, 'operation': "insertDuplicateColumn"}
	df = loadDataFrameFromCache(sessionID)
	
	try:
		dcs.clean.insertDuplicateColumn(df, columnIndex)
		saveToCache(df, sessionID)
		toReturn['changed'] = True
		toReturn['success'] = True
	except Exception as e:
		toReturn['error'] = str(e)
		toReturn['errorDescription'] = traceback.format_exc()

	try:
		requests.post("http://localhost:5000/celeryTaskCompleted/", json=toReturn, timeout=0.001)
	except:
		pass

# POSTs JSON result to Flask app on /celeryTaskCompleted/ endpoint
@celery.task()
def splitColumn(sessionID, requestID, columnIndex, delimiter, regex):
	toReturn = {'success' : False, 'requestID': requestID, 'sessionID': sessionID, 'operation': "splitColumn"}
	df = loadDataFrameFromCache(sessionID)
	
	try:
		dcs.clean.splitColumn(df, columnIndex, delimiter, regex)
		saveToCache(df, sessionID)
		toReturn['changed'] = True
		toReturn['success'] = True
	except Exception as e:
		toReturn['error'] = str(e)
		toReturn['errorDescription'] = traceback.format_exc()		

	try:
		requests.post("http://localhost:5000/celeryTaskCompleted/", json=toReturn, timeout=0.001)
	except:
		pass

# POSTs JSON result to Flask app on /celeryTaskCompleted/ endpoint
@celery.task()
def combineColumns(sessionID, requestID, columnsToCombine, seperator, newName, insertIndex):
	toReturn = {'success' : False, 'requestID': requestID, 'sessionID': sessionID, 'operation': "combineColumns"}
	df = loadDataFrameFromCache(sessionID)
	
	try:
		dcs.clean.combineColumns(df, columnsToCombine, seperator, newName, insertIndex)
		saveToCache(df, sessionID)
		toReturn['changed'] = True
		toReturn['success'] = True
	except Exception as e:
		toReturn['error'] = str(e)
		toReturn['errorDescription'] = traceback.format_exc()			

	try:
		requests.post("http://localhost:5000/celeryTaskCompleted/", json=toReturn, timeout=0.001)
	except:
		pass

# POSTs JSON result to Flask app on /celeryTaskCompleted/ endpoint
@celery.task()
def discretize(sessionID, requestID, columnIndex, cutMode, numberOfBins):
	toReturn = {'success' : False, 'requestID': requestID, 'sessionID': sessionID, 'operation': "discretize"}
	df = loadDataFrameFromCache(sessionID)
	
	try:
		dcs.clean.discretize(df, columnIndex, cutMode, numberOfBins)
		saveToCache(df, sessionID)
		toReturn['changed'] = True
		toReturn['success'] = True
	except Exception as e:
		toReturn['error'] = str(e)
		toReturn['errorDescription'] = traceback.format_exc()	

	try:
		requests.post("http://localhost:5000/celeryTaskCompleted/", json=toReturn, timeout=0.001)
	except:
		pass

# HIGHWAY TO THE DANGER ZONE
# POSTs JSON result to Flask app on /celeryTaskCompleted/ endpoint
@celery.task()
def executeCommand(sessionID, requestID, command):
	toReturn = {'success' : False, 'requestID': requestID, 'sessionID': sessionID, 'operation': "executeCommand"}
	df = loadDataFrameFromCache(sessionID)
	
	try:
		dcs.clean.executeCommand(df, command)
		saveToCache(df, sessionID)
		toReturn['changed'] = True
		toReturn['success'] = True
	except Exception as e:
		toReturn['error'] = str(e)
		toReturn['errorDescription'] = traceback.format_exc()	

	try:
		requests.post("http://localhost:5000/celeryTaskCompleted/", json=toReturn, timeout=0.001)
	except:
		pass

# POSTs response to flask app on /celeryTaskCompleted/ endpoint
@celery.task()
def metadata(request):
	toReturn = {'success' : False, 'requestID': request["requestID"], 'sessionID': request["sessionID"], 'operation': "metadata"}
	# start = datetime.datetime.now()
	df = loadDataFrameFromCache(request["sessionID"])
	# print("Metadata: Loaded HDF from cache in ", str(datetime.datetime.now() - start))

	if df is not None:
		if "filterColumnIndices" in request and type(request["filterColumnIndices"]) is list and "filterType" in request:
			# filtered metadata
			if request["filterType"] == "invalid":
				df = dcs.load.rowsWithInvalidValuesInColumns(df, request["filterColumnIndices"])
			elif request["filterType"] == "outliers":
				df = dcs.load.outliersTrimmedMeanSd(df, request["filterColumnIndices"], request.get("outliersStdDev", 2), request.get("outliersTrimPortion", 0))
			elif request["filterType"] == "duplicates":
				df = dcs.load.duplicateRowsInColumns(df, request["filterColumnIndices"])

		if "searchColumnIndices" in request and type(request["searchColumnIndices"]) is list and "searchQuery" in request:
			df = dcs.view.filterWithSearchQuery(df, request["searchColumnIndices"], request["searchQuery"], request["searchIsRegex"] if "searchIsRegex" in request else False)
		
		toReturn['success'] = True
		toReturn['undoAvailable'] = undoAvailable(request["sessionID"])
		toReturn['dataSize'] = { 'rows': df.shape[0], 'columns': df.shape[1] }
		toReturn['columns'] = []
		toReturn['columnInfo'] = {}
		for index, column in enumerate(df.columns):
			toReturn['columns'].append(column)
			information = {}
			information['index'] = index
			if np.issubdtype(df[column].dtype, np.integer):
				information['dataType'] = 'int'
			elif np.issubdtype(df[column].dtype, np.float):
				information['dataType'] = 'float'
			elif np.issubdtype(df[column].dtype, np.datetime64):
				information['dataType'] = 'datetime'
			elif df[column].dtype == np.object:
				information['dataType'] = 'string'
			else:
				information['dataType'] = str(df[column].dtype)
			information['invalidValues'] = df[column].isnull().sum()
			toReturn['columnInfo'][column] = information

	try:
		requests.post("http://localhost:5000/celeryTaskCompleted/", json=toReturn, timeout=0.001)
	except:
		pass

@celery.task()
def data(request):
	toReturn = {'success' : False, 'requestID': request["requestID"], 'sessionID': request["sessionID"], 'operation': "data"}
	df = loadDataFrameFromCache(request["sessionID"])
	if df is not None:
		try:
			if "rowIndexFrom" in request and "rowIndexTo" in request and "columnIndexFrom" in request and "columnIndexTo" in request:
				if "filterColumnIndices" in request and type(request["filterColumnIndices"]) is list:
					if request["filterType"] == "invalid":
						df = dcs.load.rowsWithInvalidValuesInColumns(df, request["filterColumnIndices"])
					elif request["filterType"] == "outliers":
						df = dcs.load.outliersTrimmedMeanSd(df, request["filterColumnIndices"], request.get("outliersStdDev", 2), request.get("outliersTrimPortion", 0))
					elif request["filterType"] == "duplicates":
						df = dcs.load.duplicateRowsInColumns(df, request["filterColumnIndices"])

				if "searchColumnIndices" in request and type(request["searchColumnIndices"]) is list and "searchQuery" in request:
					df = dcs.view.filterWithSearchQuery(df, request["searchColumnIndices"], request["searchQuery"], request.get("searchIsRegex", False))
		
				if "sortColumnIndex" in request and type(request["sortColumnIndex"]) is int and request["sortColumnIndex"] >= 0 and request["sortColumnIndex"] < len(df.columns):
					df.sort_values(df.columns[request["sortColumnIndex"]], ascending=request.get("sortAscending", True), inplace=True)

				data = dcs.load.dataFrameToJSON(df, request["rowIndexFrom"], request["rowIndexTo"], request["columnIndexFrom"], request["columnIndexTo"])

				if data is not None:
					toReturn['success'] = True
					toReturn['data'] = data
		except:
			pass
	try:
		requests.post("http://localhost:5000/celeryTaskCompleted/", json=toReturn, timeout=0.001)
	except:
		pass

# POSTs response to flask app on /celeryTaskCompleted/ endpoint
@celery.task()
def analyze(sessionID, requestID, column):
	toReturn = {'success' : False, 'requestID': requestID, 'sessionID': sessionID, 'operation': "analyze"}
	df = loadDataFrameFromCache(sessionID)
	print('requesting analysis for %s' % column)

	try:
		toReturn['data'] = dcs.analyze.analysisForColumn(df, column)
		print('got analysis for %s' % column)
		toReturn['success'] = True
	except Exception as e:
		toReturn['error'] = str(e)
		toReturn['errorDescription'] = traceback.format_exc()	
		print(str(e))
		print(traceback.format_exc())

	try:
		requests.post("http://localhost:5000/celeryTaskCompleted/", json=toReturn, timeout=0.001)
	except:
		pass

# POSTs response to flask app on /celeryTaskCompleted/ endpoint
@celery.task()
def visualize(request):
	toReturn = {'success' : False, 'requestID': request["requestID"], 'sessionID': request["sessionID"], 'operation': "visualize"}
	df = loadDataFrameFromCache(request["sessionID"])

	try:
		if request["type"] == "histogram" and "columnIndices" in request:
			toReturn.update(dcs.view.histogram(df, request["columnIndices"], request))
			toReturn['success'] = True
		elif request["type"] == "scatter" and "xColumnIndex" in request and "yColumnIndices" in request:
			toReturn.update(dcs.view.scatter(df, request["xColumnIndex"], request["yColumnIndices"], request))
			toReturn['success'] = True
		elif request["type"] == "line" and "xColumnIndex" in request and "yColumnIndices" in request:
			toReturn.update(dcs.view.line(df, request["xColumnIndex"], request["yColumnIndices"], request))
			toReturn['success'] = True
		elif request["type"] == "date" and "xColumnIndex" in request and "yColumnIndices" in request:
			toReturn.update(dcs.view.date(df, request["xColumnIndex"], request["yColumnIndices"], request))
			toReturn['success'] = True
		elif request["type"] == "frequency" and "columnIndex" in request:
			toReturn.update(dcs.view.frequency(df, request["columnIndex"], request))
			toReturn['success'] = True
		elif request["type"] == "pie" and "columnIndex" in request:
			toReturn.update(dcs.view.pie(df, request["columnIndex"], request))
			toReturn['success'] = True
	except Exception as e:
		toReturn['error'] = str(e)
		toReturn['errorDescription'] = traceback.format_exc()	

	try:
		requests.post("http://localhost:5000/celeryTaskCompleted/", json=toReturn, timeout=0.001)
	except:
		pass