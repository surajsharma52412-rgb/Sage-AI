import React, { useState } from 'react';
import { submitApplication } from '../api/applications';
import { toast } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';
import './SubmitApplication.css';

const SubmitApplication: React.FC = () => {
  const [details, setDetails] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const res = await submitApplication(details);
      if (res.success) {
        toast.success('Application submitted successfully!');
      } else {
        toast.error(res.message || 'Failed to submit application');
      }
    } catch (error) {
      console.error(error);
      toast.error('An unexpected error occurred');
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="submit-application">
      <h2>Submit Application</h2>
      <form onSubmit={handleSubmit}>
        <textarea
          placeholder="Enter your application details here..."
          value={details}
          onChange={(e) => setDetails(e.target.value)}
          required
        />
        <button type="submit" disabled={loading}>
          {loading ? 'Submitting...' : 'Submit'}
        </button>
      </form>
    </section>
  );
};

export default SubmitApplication;
