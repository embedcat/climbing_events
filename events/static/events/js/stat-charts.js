// Set new default font family and font color to mimic Bootstrap's default styling
Chart.defaults.global.defaultFontFamily = '-apple-system,system-ui,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif';
Chart.defaults.global.defaultFontColor = '#292b2c';

backgroundColors = ['#0d6efd', '#ffc107', '#dc3545', '#198754', '#d63384', '#6f42c1', '#0dcaf0', '#fd7e14', '#20c997', '#6610f2'];

function drawBarChart(id, data) {
    var ctx = document.getElementById(id);
    var myLineChart = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: data.labels,
        datasets: [{
          backgroundColor: backgroundColors,
          borderColor: "rgba(2,117,216,1)",
          data: data.data,
        }],
      },
      options: {
        scales: {
          yAxes: [{
            ticks: {
              min: 0,
            },
          }],
        },
        legend: {
          display: false
        }
      }
    });
};

function drawDoughnutChart(id, data) {
  var ctx = document.getElementById(id);
  var myPieChart = new Chart(ctx, {
  type: 'doughnut',
  data: {
    labels: data.labels,
    datasets: [{
      data: data.data,
      backgroundColor: backgroundColors,
    }],
  },
  options: {
  }
});
};