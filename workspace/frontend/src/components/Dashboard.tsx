import React, { useEffect, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { getApplications } from '../api/applicationApi';
import toast from 'react-toastify';

const Dashboard: React.FC = () => {
    const [applications, setApplications] = useState([]);
    const [loading, setLoading] = useState(true);
    const { logout } = useAuth();

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
            } finally {
                setLoading(false);
            }
        };

        fetchApplications();
    }, []);

    return (
        <div className="dashboard-container">
            <h2>Your Applications</h2>
            {loading ? (
                <p>Loading...</p>
            ) : (
                <ul>
                    {applications.map((app: any) => (
                        <li key={app.id}>
                            <strong>Status:</strong> {app.status}<br />
                            <strong>Submitted At:</strong> {new Date(app.submitted_at).toLocaleString()}<br />
                            <strong>Details:</strong> {app.details}
                        </li>
                    ))}
                </ul>
            )}
            <button onClick={logout}>Logout</button>
        </div>
    );
};

export default Dashboard;
