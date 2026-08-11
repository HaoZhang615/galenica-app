import { Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import Overview from "./pages/Overview";
import MapPage from "./pages/MapPage";
import PharmacyDetail from "./pages/PharmacyDetail";
import Alerts from "./pages/Alerts";
import Assistant from "./pages/Assistant";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Overview />} />
        <Route path="map" element={<MapPage />} />
        <Route path="pharmacy/:id" element={<PharmacyDetail />} />
        <Route path="alerts" element={<Alerts />} />
        <Route path="assistant" element={<Assistant />} />
      </Route>
    </Routes>
  );
}
