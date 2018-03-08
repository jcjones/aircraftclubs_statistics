let list_weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
let aircraft_to_color = {
  "N625LS": 'rgb(56, 75, 126)',
  "N493JL": 'rgb(18, 36, 37)',
  "N47601": 'rgb(34, 53, 101)',
  "N9014P": 'rgb(36, 55, 57)',
  // 'rgb(6, 4, 4)'
}


// Add an (x,y) point to a Trace object if it is a real point.
function insertPoint(trace, x, y) {
  if (/\d+/.test(y)) {
    trace.x.push(x);
    trace.y.push(y);
  }
}

function plot(taaDoW, numDays, lengthOfFlight, usageByWeekday,
              weekdayToWeekend, airportUtilization) {
  let defaultLayout = {
    margin: { t: 0 },
    legend: {
      xanchor: "left",
      yanchor: "top",
      x: 0,
      y: 1
    }
  };

  {
    let layout = Object.assign({
      yaxis: {
        title: "Average Aircraft Completely Unscheduled",
        dtick: 1.0, hoverformat: '.1f'
      },
      xaxis: {
        title: "Day of Week"
      },
      barmode: 'stack'
    }, defaultLayout);
    let plotDiv = document.getElementById('aaDoW');
    if (plotDiv) {
      Plotly.plot(plotDiv, taaDoW, layout);
    }
  }

  {
    let traces = [ numDays ];
    let plotDiv = document.getElementById('numDays');
    let layout = Object.assign({
      yaxis: { hoverformat: '.1f' }
    }, defaultLayout);
    if (plotDiv) {
      Plotly.plot(plotDiv, traces, layout);
    }
  }

  {
    let traces = [ lengthOfFlight ];
    let layout = Object.assign({
      yaxis: {
        title: "Number of Flights"
      },
      xaxis: {
        title: "Reservation Length in Hours", type: "log"
      },
    }, defaultLayout);

    let plotDiv = document.getElementById('lengthOfFlight');
    if (plotDiv) {
      console.log(layout);
      Plotly.plot(plotDiv, traces, layout);
    }
  }

  {
    let layout = Object.assign({barmode: 'stack'}, defaultLayout);
    let plotDiv = document.getElementById('usageByWeekday');
    if (plotDiv) {
      Plotly.plot(plotDiv, usageByWeekday, layout);
    }
  }

  {
    let layout = Object.assign({}, defaultLayout);
    let traces = [ weekdayToWeekend ];
    let plotDiv = document.getElementById('weekdayToWeekend');
    if (plotDiv) {
      Plotly.plot(plotDiv, traces, layout);
    }
  }

  {
    let layout = Object.assign({}, defaultLayout);
    let traces = [ airportUtilization ];
    let plotDiv = document.getElementById('airportUtilization');
    if (plotDiv) {
      Plotly.plot(plotDiv, traces, layout);
    }
  }
}

fetch("/wp-content/uploads/statistics/data.json")
.then((result) => {
  return result.json()
})
.then((data) => {
  console.log(data);

  let taaDoW = [];

  for (let airport of Object.keys(data['aircraft_available_by_airport_and_weekday'])) {

    let trace = { type: "bar", name: airport + " Aircraft Available",
                 x: [], y: [] };

    let available_by_airport = data['aircraft_available_by_airport_and_weekday'][airport];

    for (let dayName of Object.keys(available_by_airport)) {
      insertPoint(trace, dayName, available_by_airport[dayName]);
    }

    taaDoW.push(trace);
  }


  let numDays = { type: "box", name: "Number of Days Between Flights",
                  x: [], y: [], boxmean: true, boxpoints: "all" };
  {
    for (let aircraft of Object.keys(data['days_between_usage_by_aircraft'])) {
      for (let days of data['days_between_usage_by_aircraft'][aircraft]) {
        insertPoint(numDays, aircraft, days);
      }
    }
  }

  let lengthOfFlight = { name: "Histogram of Reservation Lengths",
                         x: [], y: [], type: "bar" };
  {
    let hours = Object.keys(data['length_of_reservation_by_hours']);
    hours.sort((x,y) => x-y);
    for (let x of hours) {
      insertPoint(lengthOfFlight, x, data['length_of_reservation_by_hours'][x]);
    }
  }

  let usageByWeekday = []
  for (let aircraft of Object.keys(data['usage_by_weekday'])) {
    let bar = { type: "bar", name: aircraft,
                marker: {
                  color: aircraft_to_color[aircraft],
                }, x: [], y: [] };
    for (let weekday of list_weekdays) {
      insertPoint(bar, weekday, data['usage_by_weekday'][aircraft][weekday]);
    }
    usageByWeekday.push(bar);
  }

  let weekdayToWeekend = { name: "Reservations on Weekdays versus Weekends",
                           type: "pie", labels: ["Weekdays", "Weekends"],
                           values: [ data['weekend_weekday_utilization']['weekday']['total'],
                                     data['weekend_weekday_utilization']['weekend']['total'] ] };

  let airportUtilization = { name: "Reservations by Airport", type: "pie",
                             labels: Object.keys(data['airport_utilization']),
                             values: Object.values(data['airport_utilization']) };

  let plotIt = plot.bind(null, taaDoW, numDays, lengthOfFlight, usageByWeekday,
                         weekdayToWeekend, airportUtilization);

  {
    let days = document.getElementById('metadataDays');
    if (days) {
      days.textContent = data['dataset_metadata']['length_days'];
    }
    let reservations = document.getElementById('metadataReservations');
    if (reservations) {
      reservations.textContent = data['dataset_metadata']['num_events'];
    }
    let start = document.getElementById('metadataStart');
    if (start) {
      start.textContent = data['dataset_metadata']['start_date'];
    }
    let end = document.getElementById('metadataEnd');
    if (end) {
      end.textContent = data['dataset_metadata']['end_date'];
    }

  }

  if (document.readyState === "complete") {
    plotIt();
  } else {
    window.addEventListener("load", plotIt);
  }

})
.catch((problem) => {
  console.log("Problem:", problem);
});