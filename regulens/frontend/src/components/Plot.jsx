import createPlotlyComponent from "react-plotly.js/factory";
import Plotly from "plotly.js-basic-dist-min";

const Plot = createPlotlyComponent(Plotly);

export default function Chart({ data, layout = {}, height = 260 }) {
  return (
    <Plot
      data={data}
      layout={{ autosize: true, height, margin: { l: 40, r: 10, t: 10, b: 30 }, paper_bgcolor: "rgba(0,0,0,0)",
        plot_bgcolor: "rgba(0,0,0,0)", font: { family: "IBM Plex Sans, sans-serif", size: 12, color: "#12202B" },
        legend: { orientation: "h" }, ...layout }}
      config={{ displayModeBar: false, responsive: true }}
      style={{ width: "100%" }}
      useResizeHandler
    />
  );
}
