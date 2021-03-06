import pandas as pd
import numpy as np
import json
import traceback
import random
import chardet
import os

def guessEncoding(filename):
	"""Guesses encoding of a file. 

	Uses chardet library to guess the text encoding of a file, and returns a guess if confidence > 80%. 

	Args:
		filename (str): path to file

	Returns:
		str: Python text encoding string e.g. 'utf-8' and 'latin-1'
	"""

	file = open(filename, "rb")
	while True:
		data = file.read(1024)
		if len(data) == 0:
			break
		guess = chardet.detect(data)
		if guess['confidence'] > 0.80:
			encoding = guess['encoding']
			break
	file.close()

	return "utf-8" if encoding is None else encoding

def convertEncoding(filename, source="utf-8", destination="utf-8", buffer=1024):
	"""Converts a file on disk to specified text encoding in-place

	The function iterates over the file in blocks, specified by number of bytes in ``buffer`` parameter which defaults to 1024

	Args:
		filename (str): path to file
		source (str, optional): original text encoding of file
		destination (str, optional): text encoding to convert to
		buffer (int): conversion iteration block size

	Returns:
		bool: True if successful, False otherwise
	"""

	try:
		temp = open(filename + '.tmp', 'wb')
		file = open(filename, 'rb')
		while True:
			data = file.read(buffer)
			if len(data) == 0:
				break
			temp.write(data.decode(source, "replace").encode(destination, "replace"))
		file.close()
		temp.close()
		os.remove(filename)
		os.rename(filename + '.tmp', filename)
		return True
	except:
		return False

# Returns Pandas.DataFrame on successful conversion, None on failure
def CSVtoDataFrame(filename, header=0, initialSkip=0, sampleSize=100, seed=None, headerIncluded=True):
	"""Initializes a ``pandas.DataFrame`` object by reading a CSV file from disk

	Note that lines with missing commas/rows will be automatically discarded and lines with extra commas/rows will be automatically truncated to proper length.  

	Args:
		filename (str): path to CSV file
		header (int, optional): line number of row which contains column headers
		initialSkip (int): number of lines to skip (beginning of file)
		sampleSize (int, optional): percentage of lines to sample, must be between 0 and 100. If set to 100, no sampling will be performed.  
		seed (hashable, optional): for deterministic/reproducible sampling if sampling enabled
		headerIncluded (bool, optional): if ``False``, columns will not be named based on any row. If ``True``, ``header`` parameter will be ignored

	Returns:
		pandas.DataFrame: pandas.DataFrame on success, or None on failure
	"""

	if convertEncoding(filename, guessEncoding(filename), "utf-8") is False:
		return None

	try:
		numberOfLines = sum(1 for line in open(filename))
		header = 0 if headerIncluded else None
		initialSkip = 0 if initialSkip > numberOfLines else initialSkip
		dataStartLine = initialSkip + (1 if headerIncluded else 0)
		if seed is None:
			random.seed(seed)
		linesToSkipIdx = []
		if sampleSize < 100 and sampleSize > 0:
			linesToSkipIdx = random.sample(range(dataStartLine, numberOfLines-1), int((numberOfLines-initialSkip)*((100-sampleSize)/100.0)))
		if initialSkip > 0:
			for i in range(0, initialSkip):
				linesToSkipIdx.append(i)
	except Exception as e:
		print(str(e))
		return None

	data = None
	if filename:
		try:
			newList = []
			data = pd.read_csv(filename, header=header, skiprows=linesToSkipIdx, engine='c', error_bad_lines=False)
			for columns in data.columns:
				newList.append(str(columns))
			data.columns = newList

		except Exception as e:
			print(str(e))
			return None

	return data if type(data) is pd.DataFrame else None


def JSONtoDataFrame(filename, sampleSize=100, seed=None):
	"""Initializes a ``pandas.DataFrame`` object by reading a JSON file from disk

	Args:
		filename (str): path to JSON file
		sampleSize (int, optional): percentage of lines to sample, must be between 0 and 100. If set to 100, no sampling will be performed.  
		seed (int, optional): for deterministic/reproducible sampling if sampling enabled

	Returns:
		pandas.DataFrame: pandas.DataFrame on success, or None on failure
	"""
	
	if convertEncoding(filename, guessEncoding(filename), "utf-8") is False:
		return None

	sampleSize = sampleSize/100
	data = None
	if filename:
		try:
			intermediateData = pd.read_json(filename, orient='records')
			if sampleSize < 1 and sampleSize > 0:
				if type(seed) is not None:
					seed = int(seed)
				data = intermediateData.sample(frac=sampleSize, random_state=seed)
				data.sort_index(inplace = True)
				data = data.reset_index(drop = True)
			else:
				data = intermediateData
		except Exception as e:
			print(str(e))
			return None

	return data if type(data) is pd.DataFrame else None

def XLSXtoDataFrame(filename, initialSkip=0, sampleSize=100, seed=None, headerIncluded=True):
	"""Initializes a ``pandas.DataFrame`` object by reading an Excel file from disk

	The function supports loading both .XLS and .XLSX files. 

	Args:
		filename (str): path to Excel file
		initialSkip (int): number of lines to skip (beginning of file)
		sampleSize (int, optional): percentage of lines to sample, must be between 0 and 100. If set to 100, no sampling will be performed.  
		seed (int, optional): for deterministic/reproducible sampling if sampling enabled
		headerIncluded (bool, optional): if ``False``, columns will not be named based on any row 

	Returns:
		pandas.DataFrame: pandas.DataFrame on success, or None on failure
	"""

	sampleSize = sampleSize/100
	data = None
	if filename:
		try:
			header = 0 if headerIncluded else None
			intermediateData = pd.read_excel(filename, skiprows = int(initialSkip), header=header)
			newList = []
			for columns in intermediateData.columns:
				newList.append(str(columns))
			intermediateData.columns = newList
			if sampleSize < 1 and sampleSize > 0:
				if type(seed) is not None:
					seed = int(seed)
				data = intermediateData.sample(frac=sampleSize, random_state=seed)
				data.sort_index(inplace = True)
				data = data.reset_index(drop = True)
			else:
				data = intermediateData
		except Exception as e:
			print(str(e))
			return None
	return data if type(data) is pd.DataFrame else None

# Returns JSON : str on successful conversion or False on failure
def dataFrameToJSON(df, rowIndexFrom=None, rowIndexTo=None, columnIndexFrom=None, columnIndexTo=None):
	if type(df) is not pd.DataFrame:
		return None

	if rowIndexFrom is None and rowIndexTo is None and columnIndexFrom is None and columnIndexTo is None:
		rowIndexFrom = 0
		rowIndexTo = df.shape[0] - 1
		columnIndexFrom = 0
		columnIndexTo = df.shape[1] - 1

	if type(rowIndexFrom) is not int or type(rowIndexTo) is not int or type(columnIndexFrom) is not int or type(columnIndexTo) is not int:
		return None
	if rowIndexFrom < 0 or rowIndexFrom > df.shape[0] or rowIndexTo < 0 or rowIndexTo > df.shape[0] or columnIndexFrom < 0 or columnIndexFrom > df.shape[1] or columnIndexFrom < 0 or columnIndexFrom > df.shape[1]:
		return None
		
	newDF = pd.DataFrame()
	for index in range(columnIndexFrom, columnIndexTo + 1):
		columnName = df.columns[index]
		if "__original__b0YgCpYKkWwuJKypnOEZeDJM8__original__" not in columnName:
			if "%s%s" % (columnName, "__original__b0YgCpYKkWwuJKypnOEZeDJM8__original__") in df.columns:
				# column holds failed conversions
				mergedColumn = df[columnName][rowIndexFrom: rowIndexTo + 1].astype('object')
				originalColumn = df["%s%s" % (columnName, "__original__b0YgCpYKkWwuJKypnOEZeDJM8__original__")][rowIndexFrom: rowIndexTo + 1]

				missingIndices = [index for (index, isnull) in originalColumn.isnull().iteritems() if isnull] 
				for index in missingIndices:
					mergedColumn[index] = "%s (original)" % originalColumn[index]

				newDF[columnName] = mergedColumn
			else:
				# normal column
				newDF[columnName] = df[columnName][rowIndexFrom:rowIndexTo + 1]

	return newDF.to_json(orient="split", date_format="iso", force_ascii=False)

# Returns True on successful rename, False on failure
def renameColumn(df, column, newName):
	if (isinstance(column, basestring) and isinstance(newName, basestring)) and column in df.columns:
		df.rename(columns={column: newName}, inplace=True)

# Returns True on successful rename, False on failure
def emptyStringToNan(df, columnIndex):
	try:
		df[df.columns[columnIndex]].replace(to_replace="", value=np.nan, inplace=True)
		return True
	except:
		pass # Returns True on successful removes, False on failure
	return False

# Returns True on successful rename, False on failure
def newCellValue(df, columnIndex, rowIndex, newValue):
	try:
		if (df[df.columns[columnIndex]].dtype == np.float64):
			try:
				newValue = float(newValue)
			except ValueError:
				pass
		elif (df[df.columns[columnIndex]].dtype == np.int64):
			try:
				newValue = int(float(newValue))
			except ValueError:
				pass
		df.loc[rowIndex, df.columns[columnIndex]] = newValue;
		return True
	except Exception as e:
		print(str(e))
		return False

# Returns True on successful removal of rows, False on failure
def removeRows(df, rowIndices):
	rowIndices = [df.index[x] for x in rowIndices]
	for index in rowIndices:
		df.drop(index, inplace=True)

	df.reset_index(drop=True, inplace=True)

# Returns True on successful removal of rows, False on failure
def removeColumns(df, columnIndices):
	df.drop(columnIndices, axis=1, inplace=True)
	df.reset_index(drop=True, inplace=True)

# Returns Pandas.DataFrame containing rows which have invalid values in all (not any) specified columns
# Returns None on failure
def rowsWithInvalidValuesInColumns(df, columnIndices):
	if type(df) is pd.DataFrame and type(columnIndices) is list and len(columnIndices) > 0:
		try:
			for columnIndex in columnIndices:
				columnName = df.columns[columnIndex]
				df = df[df[columnName].isnull()]
			return df
		except:
			print(traceback.format_exc())
	return None

# Returns Pandas.DataFrame containing rows which are duplicates in all (not any) specified columns
# Returns None on failure
def duplicateRowsInColumns(df, columnIndices):
	if type(df) is pd.DataFrame and type(columnIndices) is list and len(columnIndices) > 0:
		try:
			columnNames = []
			for columnIndex in columnIndices:
				columnNames.append(df.columns[columnIndex])
			df = df[df.duplicated(columnNames, keep=False)]
			df.sort_values(df.columns[columnIndices[0]], inplace=True)
			return df
		except:
			print(traceback.format_exc())
	return None

# Returns Pandas.DataFrame containing rows which are outliers using trimmed mean and standard deviation in all (not any) specified columns
# Returns None on failure
def outliersTrimmedMeanSd(df, columnIndices, r=2, k=0):
	if type(df) is pd.DataFrame and type(columnIndices) is list and len(columnIndices) > 0:
		try:
			rec_len = len(df)
			start_ix = int(rec_len * k)
			fin_ix = rec_len - start_ix
			dfx = df.copy()
			for columnIndex in columnIndices:
				columnName = df.columns[columnIndex]
				dfs = df.sort_values(columnName)
				trimmed_mean = dfs[columnName][start_ix:fin_ix].mean()
				trimmed_std_r = r * dfs[columnName][start_ix:fin_ix].std()
				dfx = dfx[(dfx[columnName] >= (trimmed_mean + trimmed_std_r)) | (dfx[columnName] <= (trimmed_mean - trimmed_std_r))]
			return dfx
		except:
			print(traceback.format_exc())
	return None

# Returns Pandas.Series with converted values
def dataFrameColumnAsNumericType(df, column):
	return pd.to_numeric(df[column], errors="coerce")

def changeColumnDataType(df, column, newDataType, dateFormat=None): 
	if type(df) is pd.DataFrame and isinstance(newDataType, basestring) and isinstance(column, basestring) and column in df.columns:
		newdtype = np.dtype(newDataType) if newDataType != "datetime" else np.dtype('datetime64') 
		if issubclass(newdtype.type, np.character):
			if df[column].dtype.type == np.datetime64:
				# datetime to string in iso format
				df[column] = df[column].apply(lambda x: "" if pd.isnull(x) else x.isoformat())
				# replace empty string with np.nan
				df[column].replace(to_replace="", value=np.nan, inplace=True)
			else:
				# simple conversion to string
				df[column] = df[column].astype(newdtype)
		elif issubclass(df[column].dtype.type, np.number) and issubclass(newdtype.type, np.number):
			# simple conversion from number to number
			# BUT WILL fail if column with dtype float contains infinity or negative infinity
			converted = df[column].astype(newdtype)
			df[column] = converted
		elif issubclass(newdtype.type, np.number):
			# conversion from string to number
			converted = pd.to_numeric(df[column], errors="coerce").astype(newdtype)
			df[column] = converted
		elif issubclass(newdtype.type, np.datetime64):
			# conversion from string to date
			converted = None
			if dateFormat is None:
				converted = pd.to_datetime(df[column], infer_datetime_format=True)
			else:
				converted = pd.to_datetime(df[column], format=dateFormat)
			df[column] = converted