import React from 'react';
import { Route, Switch, Redirect } from 'react-router-dom';
import Header from './components/Header';
import Footer from './components/Footer';
import Home from './pages/Home';
import Login from './pages/Login';
import Register from './pages/Register';
import Dashboard from './pages/Dashboard';
import SubmitApplication from './pages/SubmitApplication';
import ViewApplications from './pages/ViewApplications';
import ProtectedRoute from './components/ProtectedRoute';

const App: React.FC = () => {
  return (
    <div className="app">
      <Header />
      <main>
        <Switch>
          <Route path="/" exact component={Home} />
          <Route path="/login" component={Login} />
          <Route path="/register" component={Register} />
          <ProtectedRoute path="/dashboard" component={Dashboard} />
          <ProtectedRoute path="/submit-application" component={SubmitApplication} />
          <ProtectedRoute path="/view-applications" component={ViewApplications} />
          <Redirect to="/" />
        </Switch>
      </main>
      <Footer />
    </div>
  );
};

export default App;
