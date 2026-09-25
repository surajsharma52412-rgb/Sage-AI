import axios from 'axios';
import { useAuth } from '../context/AuthContext';

const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000/api';

export const getApplications = async () => {
    try {
        const response = await axios.get(`${API_BASE_URL}/applications`);
        return response.data;
    } catch (error) {
        throw error.response ? error.response.data : error;
    }
};

export const submitApplication = async (details: string) => {
    try {
        const response = await axios.post(`${API_BASE_URL}/applications`, { details });
        return response.data;
    } catch (error) {
        throw error.response ? error.response.data : error;
    }
};
