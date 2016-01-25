angular.module('dcs.directives').directive('cleanSidebarMissingValues', ['$rootScope', 'session', function($rootScope, session) {
	return {
		restrict: 'E',
		scope: true,
		templateUrl: "directives/clean.sidebar.missingValues.html",
		link: function(scope, element, attr) {
			scope.$watch('selectedCells', function(newSelection, oldSelection)
			{
				scope.update();
			}, true);

			$rootScope.$watch('dataTypes', function(newVal, oldVal)
			{
				scope.update()
			}, true);

			scope.update = function()
			{
				if(typeof scope.selectedCells === 'object')
				{
					scope.shouldShow = typeof scope.selectedCells === 'object' ? scope.selectionIsColumn(scope.selectedCells) : false;
					var dataType = $rootScope.dataTypes[scope.columns[scope.selectedCells.columnStart]];
					scope.shouldShowInterpolation = scope.interpolationAllowedDataTypes.indexOf(dataType) >= 0;
				}
			}

			scope.init = function()
			{
				scope.interpolationAllowedDataTypes = ['int64', 'float64', 'datetime64'];
				scope.missingValsInterpolationMethods = ['Linear', 'Quadratic', 'Cubic', 'Barycentric'];
				scope.update();
			}

			scope.init();

			scope.requestFill =
				function(method)
				{
					session.fillDown(scope.selectedCells.columnStart, scope.selectedCells.columnEnd, method,
						function(success)
						{
							if(!success)
							{
								alert("fill with nearest value failed");
								scope.hideToast();
							}
							else
							{
								scope.showToast("Successfully filled missing values", 3000);
							}
						});
					scope.showToast("Applying Changes...");
				};

			scope.interpolate =
				function()
				{
					method = scope.interpolationMethod;
					session.interpolate(scope.selectedCells.columnStart, method,
						function(success)
						{
							if(!success)
							{
								alert("interpolation failed");
								scope.hideToast();
							}
							else
							{
								scope.showToast("Successfully interpolated values", 3000);
							}
						});
					scope.showToast("Applying Changes...");
				};

			scope.fillWithCustomValue =
				function()
				{
					newValue = scope.customNewValue;
					session.fillWithCustomValue(scope.selectedCells.columnStart, newValue,
						function(success)
						{
							if(!success)
							{
								alert("fill with custom value failed");
								scope.hideToast();
							}
							else
							{
								scope.showToast("Successfully filled missing values", 3000);
							}
						});
					scope.showToast("Applying Changes...");
				}

			scope.fillWithAverage =
				function(metric)
				{
					session.fillWithAverage(scope.selectedCells.columnStart, metric,
						function(success)
						{
							if(!success)
							{
								alert("fill with average value failed");
								scope.hideToast();
							}
							else
							{
								scope.showToast("Successfully filled missing values", 3000);
							}
						});
					scope.showToast("Applying Changes...");
				}
		}
	}
}]);