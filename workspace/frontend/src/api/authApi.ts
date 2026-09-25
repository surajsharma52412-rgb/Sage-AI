import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000/api';

export const loginUser = async (email: string, password: string) => {
    try {
        const response = await axios.post(`${API_BASE_URL}/auth/login`, { email, password });
        return response.data;
    } catch (error) {
        throw error.response ? error.response.data : error;
    }
};

export const registerUser = async (email: string, password: string, role: string) => {
    try {
        const response = await axios.post(`${API_BASE_URL}/auth/register`, { email, password, role });
        return response.data;
    } catch (error) {
        throw error.response ? error.response.data : error;
    }
};
