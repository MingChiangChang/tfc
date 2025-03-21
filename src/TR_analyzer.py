import sys
sys.path.insert(0, '/Users/ming/Desktop/Code/tfc/src')
import json
from functools import partial
from multiprocessing import Pool

import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import least_squares
# from scipy.interpolate import make_smoothing_spline
# from scipy.ndimage import gaussian_filter1d

from error_funcs import oned_gaussian_func, two_lorentz, two_gaussian

class Base_TR_analyzer():
    """ Base clasee for TR analyzers. Geared with fitting functions """

    def __init__(self, x, y, velocity, power, live_images, bg_images):

        self.x = x
        self.y = y
        self.velocity = velocity
        self.power = power

        self.live_images = live_images
        self.bg_images = bg_images

        self.is_analyzed = False

    def check_analysis_state(self):
        assert self.is_analyzed, "The data has not been analyzed."

    @property
    def condition_str(self):
        return f"{int(self.velocity)}mm_{int(self.power)}W"

    def fit_gaussians(self, data, x0, bounds=None, plot=False):
        """ Batch version of fit_guassian"""
        r = []
        for d in data:
            xx = self.fit_gaussian(d, x0, bounds, plot)
            r.append(xx)
        return r

    def fit_batch(self, data, method, x0 = None, bounds=None, plot=False):
        """ Batch version of fit_guassian"""
        r = []
        for d in data:
            xx = method(d, x0, bounds, plot)
            r.append(xx)
        return r


    def fit_gaussian(self, data, x0=None, bounds=None, plot=False):
        """ Fit a gaussian shape to the data """

        x = np.arange(data.shape[0])
        err = lambda p: np.ravel(oned_gaussian_func(*p)(x)) - data
        if x0 is None:
            x0 = [0.0, data.shape[0] // 2, data.shape[0] // 2]

        if bounds is not None:
            pfit = least_squares(err, x0, bounds=bounds)
        else:
            pfit = least_squares(err, x0)
        if True:
            plt.plot(data)
            plt.plot(oned_gaussian_func(*pfit.x)(x))
            plt.title(f"{str(pfit.x[0])} {str(pfit.x[1])} {str(pfit.x[2])}")
            plt.show()

        return pfit.x    

    def fit_two_lorentz(self, data, x0=None,  bounds=None, plot=False):
        """ Fit an asymmetric Lorentzian function to the data """

        x = np.arange(data.shape[0])
        err = lambda p: np.ravel(two_lorentz(*p)(x)) - data

        # x0 = [0.0, data.shape[0] // 2, data.shape[0] // 2, data.shape[0] // 2]
        if x0 is None:
            x0 = [0.15, 500., 200., 200.]
        if bounds is None:
            # VGA
            bounds = ([0., 300., 100., 100.], [0.5, 700., 800., 800.])
            # FF
            # bounds = ([0., 300., 100., 100.], [0.5, 800., 600., 500.])

        pfit = least_squares(err, x0, bounds=bounds)
        
        if plot:
            plt.plot(data)
            plt.plot(two_lorentz(*pfit.x)(x))
            plt.show()

        return pfit.x

    def fit_two_gaussian(self, data, x0=None, bounds=None, plot=False):
        """ Fit an asymmetric Gaussain function to the data """

        x = np.arange(data.shape[0])
        err = lambda p: np.ravel(two_gaussian(*p)(x)) - data

        # FF
        # x0 = [0., data.shape[0] // 2,  data.shape[0] // 2, data.shape[0] // 2]
        # VGA
        if x0 is None:
            x0 = [0.15, 300., 200., 200.]

        if bounds is None:
            # VGA
            bounds = ([0., 150., 100., 100.], [0.5, 450., 800., 800.])
            # FF
            # bounds = ([0., 300., 100., 100.], [0.5, 800., 600., 500.])
        pfit = least_squares(err, x0, bounds=bounds)
        
        if plot:
            plt.plot(data)
            plt.plot(two_gaussian(*pfit.x)(x))
            plt.show()

        return pfit.x




class Stripe_TR_analyzer(Base_TR_analyzer):

    def __init__(self, x, y, velocity, power, live_images, bg_images):

        super().__init__(x, y, velocity, power, live_images, bg_images)

        self.n_runs = live_images.shape[0]
        self.n_frames = live_images.shape[1]

        self.reflectance = self.get_reflectance(live_images, bg_images) 


    def get_reflectance(self, live_images, bg_images):
        r = np.zeros_like(live_images)
        for i in range(np.shape(r)[0]):
            r[i] = (live_images[i] - bg_images) / bg_images
        return r

        
    def analyze(self, x_min = 0, x_max = 480, y_min = 0, y_max=640):
        """
        Given the patch, defined by x_min, x_max, y_max and y_min, 
        this function will first fit a series of Gaussian horizontally
        and fit another Gaussian to the peak height to identify the intensity center of the laser.
        Then fit both two-sides Lorentzian and symmetric Gaussian to the horizontal slice of the profile.
        """

        reflectance_patch = self.reflectance[:,:, x_min:x_max, y_min:y_max]

        fit_results = np.array([
            # [self.fit_batch(reflectance_patch[n_run, n_frame], self.fit_gaussian,
                [self.fit_batch(reflectance_patch[n_run, n_frame], self.fit_two_lorentz,
                      bounds=([0.0, 0., 200., 200.], [0.3, y_max-y_min, (y_max-y_min), (y_max-y_min)]))
                         for n_frame in range(self.n_frames)]
                               for n_run in range(self.n_runs)
           ])


        peak_int_fit_result = np.array([
            [self.fit_gaussian(fit_results[n_run, n_frame, :, 0], 
                               bounds=([0., 0., 5.], [0.3, x_max-x_min, x_max-x_min]))
                         for n_frame in range(self.n_frames)]
                               for n_run in range(self.n_runs)
           ])

        for run in range(self.n_runs):
            for frame in range(self.n_frames):
                y = fit_results[run, frame, :, 0]
                x = np.arange(len(y))

                plt.plot(x, fit_results[run, frame, :, 0], label="raw")
                plt.plot(oned_gaussian_func(*peak_int_fit_result[run, frame])(np.arange(x_max-x_min)), label="fit")
                plt.legend()
                plt.savefig(f"{self.velocity}mm_{self.power}W_{run}_{frame}")
                plt.close()


        idx = np.round(peak_int_fit_result[:, :, 1])
        self.center = np.squeeze(x_min + np.round(peak_int_fit_result[:, :, 1]))
        self.center_fit_results = np.array([
            [fit_results[n_run, n_frame, round(peak_int_fit_result[n_run, n_frame, 1])]
                         for n_frame in range(self.n_frames)]
                               for n_run in range(self.n_runs)
           ]) # Should have a better way to do this but not critical atm

        idx = np.round(peak_int_fit_result[:,:,1]).astype(int)
        self.center = np.squeeze(x_min + np.round(peak_int_fit_result[:,:,1]))
        # FIXME: There must be a better way to do this
        self.center_fit_results = np.array([[fit_results[i, j, idx[i, j]] 
                                             for j in range(idx.shape[1])]
                                               for i in range(idx.shape[0])])
        self.center_profile = np.array([[reflectance_patch[i, j, idx[i, j]] for j in range(idx.shape[1])] for i in range(idx.shape[0])])

        self.two_lorentz_pfit = np.array([[self.fit_two_lorentz(self.center_profile[i, j]) for j in range(idx.shape[1])] for i in range(idx.shape[0])])
        # self.two_gaussian_pfit = self.fit_two_gaussian(self.center_profile)

        self.is_analyzed = True

    
    ####### Plotting functions ############
    def plot_heatmap(self, save=False):
        for i in range(self.reflectance.shape[0]):
            sc = plt.imshow(self.reflectance[i])
            plt.title('f{self.condition_str}_{i}')
            plt.colorbar(sc)

        if save:
            plt.savefig(f"{self.condition_str}_heatmap.png")
            plt.close()
        else:
            plt.show()

                         
    def plot_dr_r(self, save=False):
        self.check_analysis_state()
        # print(self.center_fit_results[:,:,0].shape)
        for i in range(self.center_fit_results.shape[0]):
            plt.plot(self.center_fit_results[i, :, 0], marker='o', label=f'Run {i}')
            plt.xlabel('frame #')
            plt.ylabel('dr/r')

        plt.title(f'{self.condition_str}_dr/r')
        plt.legend()

        if save:
            plt.savefig(f"{self.condition_str}_peak_dr_r.png")
            plt.close()
        else:
            plt.show()

    def plot_center_pos(self, save=False):
        self.check_analysis_state()
        for i in range(self.center_fit_results.shape[0]):
            plt.plot(self.center_fit_results[i, :, 1], marker='o', label=f'Run {i}')
            plt.xlabel('frame #')
            plt.ylabel('Center position (pxl)')

        plt.title(f'{self.condition_str} Center position in x')
        plt.legend()

        if save:
            plt.savefig(f"{self.condition_str}_pos.png")
            plt.close()
        else:
            plt.show()

    def plot_sigma(self, save=False):
        self.check_analysis_state()
        for i in range(self.center_fit_results.shape[0]):
            plt.plot(self.center_fit_results[i, :, 2], marker='o', label=f'Run {i}')
            plt.xlabel('frame #')
            plt.ylabel('sigma (pxl)')

        plt.title(f'{self.condition_str} sigma')
        plt.legend()

        if save:
            plt.savefig(f"{self.condition_str}_sigma.png")
            plt.close()
        else:
            plt.show()

    ######## Saving functions ##########3
    def save_npy(self):
        self.check_analysis_state()
        np.save(self.condition_str, self.center_fit_results)

    def save_json(self, fn=None):
        self.check_analysis_state()

        data_dict = {}
        data_dict['x'] = self.x
        data_dict['y'] = self.y
        data_dict['velocity'] = float(self.velocity)
        data_dict['power'] = float(self.power)
        data_dict["peak"] = self.two_lorentz_pfit[:,:,0].tolist()
        data_dict["peak_idx"] = self.two_lorentz_pfit[:,:1].tolist()
        data_dict["left_width"] = self.two_lorentz_pfit[:,:,2].tolist()
        data_dict["right_width"] = self.two_lorentz_pfit[:,:,3].tolist()

        data_dict["gaussian_peak"] = self.center_fit_results[:,:,0].tolist()
        data_dict["gaussian_peak_idx"] = self.center_fit_results[:,:1].tolist()
        data_dict["gaussian_width"] = self.center_fit_results[:,:,2].tolist()

        if fn is None:
            fn = f"{self.condition_str}.json"

        with open(fn, 'w') as f:
            json.dump(data_dict, f)





class Single_TR_analyzer(Base_TR_analyzer):

    def __init__(self, x, y, velocity, power, live_image, bg_image):

        super().__init__(x, y, velocity, power, live_image, bg_image)

        self.live_image = live_image
        self.bg_image = bg_image
        self.reflectance = (live_image - bg_image ) / bg_image
        # print('reflectance:', self.reflectance.shape)

    def analyze_single_frame(self,
                             x_min = 0, x_max = 480,
                             y_min = 0, y_max = 640):

        reflectance_patch = self.reflectance[x_min:x_max, y_min:y_max]
        self.fit_results = np.array(
                # self.fit_gaussians(reflectance_patch,
                #        bounds=([0.0, 0., 20.], [0.3, y_max-y_min, 3*(y_max-y_min)]))
                self.fit_batch(reflectance_patch, method=self.fit_two_lorentz,
                       bounds=([0.0, 0.0, 0., 20., 20.],
                         [0.1, 0.3, y_max-y_min, 3*(y_max-y_min), 3*(y_max-y_min)]))
           )

        # self.peak_int_fit_result = np.array(
        #     self.fit_gaussian(self.fit_results[:, 0],
        #                        bounds=([0., 0., 20.], [0.5, x_max-x_min-1, 200.]))
        #    )

        
        self.peak_int_fit_result = np.array(
            self.fit_two_lorentz(self.fit_results[:, 0] + self.fit_results[:, 1],
                                 x0=[0.01, 0.2, 50., 100., 100.],
                                 bounds=([0., 0., 0., 20., 20.], [0.1, 0.5, x_max-x_min-1, 200., 200.]))
           )

        self.center = np.squeeze(x_min + np.round(self.peak_int_fit_result[1]))
        self.center_fit_results = self.fit_results[round(self.peak_int_fit_result[1])]
        self.center_profile = reflectance_patch[round(self.peak_int_fit_result[1])]

        self.two_lorentz_pfit = self.fit_two_lorentz(self.center_profile)
        self.two_gaussian_pfit = self.fit_two_gaussian(self.center_profile)

        self.is_analyzed = True

    def plot(self, save=False, fn=None):

        self.check_analysis_state()
        plt.plot(self.center_profile)
        x = np.arange(self.center_profile.shape[0])
        plt.plot(self.two_lorentz_pfit[0] + two_lorentz(*self.two_lorentz_pfit[1:])(x), label="Lorentz")
        plt.plot(two_gaussian(*self.two_gaussian_pfit)(x), label="Gaussian", color='r')
        plt.legend()
        plt.ylim(0, .25)
        if save:
            if fn is None:
                fn = f"{self.condition_str}.png"
            plt.savefig(fn)
            plt.close()
        else:
            plt.show()

    def plot_heatmap(self, _id=0, save=False):
        plt.imshow(self.reflectance)
        plt.title(f'{self.condition_str}_{_id}')
        plt.colorbar()

        if save:
            plt.savefig(f"{self.condition_str}_{_id}_heatmap.png")
            plt.close()
        else:
            plt.show()


    def save_json(self, fn=None):

        self.check_analysis_state()

        data_dict = {}
        data_dict['x'] = float(self.x)
        data_dict['y'] = float(self.y)
        data_dict['velocity'] = float(self.velocity)
        data_dict['power'] = float(self.power)
        data_dict["lorentz_peak"] = self.two_lorentz_pfit[0]
        data_dict["lorentz_peak_idx"] = self.two_lorentz_pfit[1]
        data_dict["lorentz_left_width"] = self.two_lorentz_pfit[2]
        data_dict["lorentz_right_width"] = self.two_lorentz_pfit[3]

        data_dict["gauss_peak"] = self.two_gaussian_pfit[0]
        data_dict["gauss_peak_idx"] = self.two_gaussian_pfit[1]
        data_dict["gauss_left_width"] = self.two_gaussian_pfit[2]
        data_dict["gauss_right_width"] = self.two_gaussian_pfit[3]

        if fn is None:
            fn = f"{self.condition_str}.json" 

        with open(fn, 'w') as f:
            json.dump(data_dict, f)

