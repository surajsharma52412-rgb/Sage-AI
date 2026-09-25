import React, { useState } from 'react';
import { useHistory } from 'react-router-dom';
import { submitApplication } from '../api/applicationApi';
import toast from 'react-toastify';

const ApplicationForm: React.FC = () => {
    const [details, setDetails] = useState('');
    const [loading, setLoading] = useState(false);
    const history = useHistory();

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setLoading(true);
        try {
            const res = await submitApplication(details);
            if (res.success) {
                toast.success('Application submitted successfully!');
                history.push('/dashboard');
            } else {
                toast.error(res.message || 'Application submission failed');
            }
        } catch (error) {
            console.error(error);
            toast.error('An unexpected error occurred');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="application-form-container">
            <h2>Submit New Application</h2>
            <form onSubmit={handleSubmit}>
                <textarea value={details} onChange={e => setDetails(e.target.value)} placeholder="Enter your application details" required />
                <button type="submit" disabled={loading}>{loading ? 'Submitting...' : 'Submit Application'}</button>
            </form>
        </div>
    );
};

export default ApplicationForm;
