import numpy as np
import matplotlib.pyplot as plt

MU0 = 1.0
EPS0 = 1.0
C0 = 1 / np.sqrt(MU0*EPS0)

# Constants for permittivity regions test
EPS1 = 2.0
C1 = 1 / np.sqrt(MU0*EPS1)
R = (np.sqrt(EPS0)-np.sqrt(EPS1))/(np.sqrt(EPS0)+np.sqrt(EPS1))
T = 2*np.sqrt(EPS0)/(np.sqrt(EPS0)+np.sqrt(EPS1))

def gaussian_pulse(x, x0, sigma):
    return np.exp(-((x - x0) ** 2) / (2 * sigma ** 2))


class FDTD1D:
    def __init__(self, xE, bounds=('pec', 'pec')):
        self.xE = np.array(xE)
        self.xH = (self.xE[:-1] + self.xE[1:]) / 2.0
        self.dx = self.xE[1] - self.xE[0]
        self.bounds = bounds
        self.e = np.zeros_like(self.xE)
        self.h = np.zeros_like(self.xH)
        self.h_old = np.zeros_like(self.h)
        self.eps = np.ones_like(self.xE)  # Default permittivity is 1 everywhere
        self.cond = np.zeros_like(self.xE)  # Default conductivity is 0 everywheree
        self.condPML=np.zeros_like(self.xH) # Fake PML magnetic conductivty
        self.initialized = False
        self.energyE = []
        self.energyH = []
        self.energy = []

    def set_initial_condition(self, initial_condition):
        self.e[:] = initial_condition[:]
        self.initialized = True

    def set_permittivity_regions(self, regions):
        """Set different permittivity regions in the grid.
        
        Args:
            regions: List of tuples (start_x, end_x, eps_value) defining regions
                    with different permittivity values.
        """
        for start_x, end_x, eps_value in regions:
            start_idx = np.searchsorted(self.xE, start_x)
            end_idx = np.searchsorted(self.xE, end_x)
            self.eps[start_idx:end_idx] = eps_value

    def set_conductivity_regions(self, regions):
        """Set different conductivity regions in the grid.
        
        Args:
            regions: List of tuples (start_x, end_x, cond_a_value) defining regions
                    with different conductivity values.
        """
        for start_x, end_x, cond_value in regions:
            start_idx = np.searchsorted(self.xE, start_x)
            end_idx = np.searchsorted(self.xE, end_x)
            
            self.cond[start_idx:end_idx] = cond_value 
            
    def set_PML(self,thicknessPML,m,R0,dx):
        
        '''
        Setting the PML region and value
        (it means changing both self.cond and self.condPML)
        on the region in which it is implemented. 
        That is at both sides of the positions array with a thickness
        of thicknessPML cells.
        '''
        
        sigmaMax=(-np.log(R0)*(m+1))/(2*thicknessPML*dx)
        for i in range(0,thicknessPML):
            sigmai=sigmaMax*((thicknessPML-i)/thicknessPML)**m
            right_index= int(len(self.condPML)-1-i)
            self.condPML[i]=sigmai
            self.condPML[right_index]=sigmai
            self.cond[i]=sigmai
            self.cond[right_index]=sigmai
            
        #plt.plot(self.xH,self.condPML) #to plot the PML profile
        #plt.show()
            
            
        
            
    def step(self, dt):
        if not self.initialized:
            raise RuntimeError(
                "Initial condition not set. Call set_initial_condition first.")

        self.e_old_left = self.e[1]
        self.e_old_right = self.e[-2]
        
        '''
        Updated FDTD Scheme to implement PML and conductivity. 
        The original one is returned when self.condPML and 
        self.cond are 0 arrays (default by definition).
        '''
        self.h[:] = ( 1 / ((MU0 / dt) + (self.condPML[:] / 2)) ) * ( ( (MU0/dt) - (self.condPML[:]/2) ) * self.h[:] - 1 / self.dx * (self.e[1:] - self.e[:-1]) )
        #self.h[:] = self.h[:] - dt / self.dx / MU0 * (self.e[1:] - self.e[:-1])
        self.e[1:-1] = ( 1 / ((self.eps[1:-1] / dt) + (self.cond[1:-1] / 2)) ) * ( ( (self.eps[1:-1]/dt) - (self.cond[1:-1]/2) ) * self.e[1:-1] - 1 / self.dx * (self.h[1:] - self.h[:-1]) )

        if self.bounds[0] == 'pec':
            self.e[0] = 0.0
        elif self.bounds[0] == 'mur':
            self.e[0] = self.e_old_left + (C0*dt - self.dx) / \
                (C0*dt + self.dx)*(self.e[1] - self.e[0])
        elif self.bounds[0] == 'pmc':
            self.e[0] = self.e[0] - 2 * dt/ self.dx/ EPS0*(self.h[0])
        elif self.bounds[0] == 'periodic':
            self.e[0] = self.e[-2]
        else:
            raise ValueError(f"Unknown boundary condition: {self.bounds[0]}")

        if self.bounds[1] == 'pec':
            self.e[-1] = 0.0
        elif self.bounds[1] == 'mur':
            self.e[-1] = self.e_old_right + (C0*dt - self.dx) / \
                (C0*dt + self.dx)*(self.e[-2] - self.e[-1])
        elif self.bounds[1] == 'pmc':
            self.e[-1] = self.e[-1] + 2 * dt/self.dx / EPS0*(self.h[-1])
        elif self.bounds[1] == 'periodic':
            self.e[-1] = self.e[1]
        else:
            raise ValueError(f"Unknown boundary condition: {self.bounds[1]}")
        
        # Energy calculation
        self.energyE.append(0.5 * np.dot(self.e, self.dx * self.eps * self.e))
        self.energyH.append(0.5 * np.dot(self.h_old, self.dx * MU0 * self.h))
        self.energy.append(0.5 * np.dot(self.e, self.dx * self.eps * self.e) + 0.5 * np.dot(self.h_old, self.dx * MU0 * self.h))
        self.h_old[:] = self.h[:]
        
        '''
        # For debugging and visualization
        if not hasattr(self, 'step_counter'):
            self.step_counter = 0  # Initialize step counter if it doesn't exist

        self.step_counter += 1
        plt.axvspan(self.xE[0], self.xE[200], color='skyblue', alpha=0.05, label='zona destacada')
        plt.axvspan(self.xE[-200], self.xE[-1], color='skyblue', alpha=0.05, label='zona destacada')

        # Plot only every 10 steps (you can adjust the interval as needed)
        if self.step_counter % 10 == 0:
            plt.plot(self.xE, self.e, label='Electric Field')
            plt.plot(self.xH, self.h, label='Magnetic Field')
            plt.ylim(-1, 1)
            plt.pause(0.01)
            plt.grid()
            plt.cla()
        '''
    def run_until(self, Tf, dt):
        if not self.initialized:
            raise RuntimeError(
                "Initial condition not set. Call set_initial_condition first.")

        n_steps = int(Tf / dt)
        for _ in range(n_steps):
            
            self.step(dt)

        return self.e 

