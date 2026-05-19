import { Routes, Route, Navigate } from "react-router-dom";
import Layout from "./components/Layout.jsx";
import FirstBootModal from "./components/FirstBootModal.jsx";
import Search from "./pages/Search.jsx";
import FundDetail from "./pages/FundDetail.jsx";
import Compare from "./pages/Compare.jsx";
import Calculator from "./pages/Calculator.jsx";
import Admin from "./pages/Admin.jsx";

export default function App() {
  return (
    <>
      <FirstBootModal />
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Navigate to="/search" replace />} />
          <Route path="/search" element={<Search />} />
          <Route path="/fund/:schemeCode" element={<FundDetail />} />
          <Route path="/compare" element={<Compare />} />
          <Route path="/calculator" element={<Calculator />} />
          <Route path="/admin" element={<Admin />} />
          <Route path="*" element={<Navigate to="/search" replace />} />
        </Route>
      </Routes>
    </>
  );
}
