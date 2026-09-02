import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import HomePage from './pages/HomePage';
import ItemPage from './pages/ItemPage';
import UnsubscribePage from './pages/UnsubscribePage';

export default function App() {
  return (
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/item/:id" element={<ItemPage />} />
          <Route path="/unsubscribe/:token" element={<UnsubscribePage />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  );
}
