import React, { useEffect, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { getApplications } from '../api/applications';
import { toast } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';
import './Dashboard.css';

const Dashboard: React.FC = () => {
  const { user } = useAuth();
  const [applications, setApplications] = useState([]);

  useEffect(() => {
    const fetchApplications = async () => {
      try {
        const res = await getApplications();
        if (res.success) {
          setApplications(res.data);
        } else {
          toast.error(res.message || 'Failed to fetch applications');
        }
      } catch (error) {
        console.error(error);
        toast.error('An unexpected error occurred');
      }
    };

    fetchApplications();
  }, [user]);

  return (
    <section className="dashboard">
      <h2>Dashboard</h2>
      <p>Welcome, {user?.email}</p>
      <div className="applications-list">
        {applications.map((app: any) => (
          <div key={app.id} className="application-item">
            <h3>{app.status}</h3>
            <p>{app.details}</p>
          </div>
        ))}
      </div>
    </section>
  );
};

export default Dashboard;
