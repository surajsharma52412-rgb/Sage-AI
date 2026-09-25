import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Login from '../components/Login';
import { loginUser } from '../api/auth';

jest.mock('../api/auth');

describe('Login Component', () => {
    it('renders correctly', () => {
        render(
            <MemoryRouter>
                <Login />
            </MemoryRouter>
        );

        expect(screen.getByLabelText(/Email/i)).toBeInTheDocument();
        expect(screen.getByLabelText(/Password/i)).toBeInTheDocument();
        expect(screen.getByText(/Login/i)).toBeInTheDocument();
    });

    it('submits form successfully', async () => {
        (loginUser as jest.Mock).mockResolvedValue({ success: true, message: 'Login successful!' });

        render(
            <MemoryRouter>
                <Login />
            </MemoryRouter>
        );

        fireEvent.change(screen.getByLabelText(/Email/i), { target: { value: 'test@example.com' } });
        fireEvent.change(screen.getByLabelText(/Password/i), { target: { value: 'testpassword' } });
        fireEvent.click(screen.getByText(/Login/i));

        await waitFor(() => {
            expect(loginUser).toHaveBeenCalledWith('test@example.com', 'testpassword');
            expect(screen.getByText(/Login successful!/i)).toBeInTheDocument();
        });
    });

    it('handles login failure', async () => {
        (loginUser as jest.Mock).mockResolvedValue({ success: false, message: 'Login failed!' });

        render(
            <MemoryRouter>
                <Login />
            </MemoryRouter>
        );

        fireEvent.change(screen.getByLabelText(/Email/i), { target: { value: 'test@example.com' } });
        fireEvent.change(screen.getByLabelText(/Password/i), { target: { value: 'testpassword' } });
        fireEvent.click(screen.getByText(/Login/i));

        await waitFor(() => {
            expect(loginUser).toHaveBeenCalledWith('test@example.com', 'testpassword');
            expect(screen.getByText(/Login failed!/i)).toBeInTheDocument();
        });
    });

    it('handles unexpected error', async () => {
        (loginUser as jest.Mock).mockRejectedValue(new Error('Unexpected error'));

        render(
            <MemoryRouter>
                <Login />
            </MemoryRouter>
        );

        fireEvent.change(screen.getByLabelText(/Email/i), { target: { value: 'test@example.com' } });
        fireEvent.change(screen.getByLabelText(/Password/i), { target: { value: 'testpassword' } });
        fireEvent.click(screen.getByText(/Login/i));

        await waitFor(() => {
            expect(loginUser).toHaveBeenCalledWith('test@example.com', 'testpassword');
            expect(screen.getByText(/An unexpected error occurred/i)).toBeInTheDocument();
        });
    });
});
