from veros.core.operators import numpy as np

from veros import veros_routine, veros_kernel, run_kernel
from veros.core import numerics, utilities, isoneutral
from veros.core.operators import update, update_add, at


@veros_kernel
def explicit_vert_friction(du_mix, dv_mix, K_diss_v, kappaM, u, v, tau, maskU,
                           maskV, area_v, area_t, dxt, dxu, dzt, dzw, nz):
    """
    explicit vertical friction
    dissipation is calculated and added to K_diss_v
    """
    diss = np.zeros_like(maskU)
    flux_top = np.zeros_like(maskU)

    """
    vertical friction of zonal momentum
    """
    fxa = 0.5 * (kappaM[1:-2, 1:-2, :-1] + kappaM[2:-1, 1:-2, :-1])
    flux_top = update(flux_top, at[1:-2, 1:-2, :-1], fxa * (u[1:-2, 1:-2, 1:, tau] - u[1:-2, 1:-2, :-1, tau]) \
        / dzw[np.newaxis, np.newaxis, :-1] * maskU[1:-2, 1:-2, 1:] * maskU[1:-2, 1:-2, :-1])
    flux_top = update(flux_top, at[:, :, -1], 0.0)
    du_mix = update(du_mix, at[:, :, 0], flux_top[:, :, 0] / dzt[0] * maskU[:, :, 0])
    du_mix = update(du_mix, at[:, :, 1:], (flux_top[:, :, 1:] - flux_top[:, :, :-1]) / dzt[1:] * maskU[:, :, 1:])

    """
    diagnose dissipation by vertical friction of zonal momentum
    """
    diss = update(diss, at[1:-2, 1:-2, :-1], (u[1:-2, 1:-2, 1:, tau] - u[1:-2, 1:-2, :-1, tau]) \
        * flux_top[1:-2, 1:-2, :-1] / dzw[np.newaxis, np.newaxis, :-1])
    diss = update(diss, at[:, :, nz - 1], 0.0)
    diss = numerics.ugrid_to_tgrid(diss, dxt, dxu)
    K_diss_v += diss

    """
    vertical friction of meridional momentum
    """
    fxa = 0.5 * (kappaM[1:-2, 1:-2, :-1] + kappaM[1:-2, 2:-1, :-1])
    flux_top = update(flux_top, at[1:-2, 1:-2, :-1], fxa * (v[1:-2, 1:-2, 1:, tau] - v[1:-2, 1:-2, :-1, tau]) \
        / dzw[np.newaxis, np.newaxis, :-1] * maskV[1:-2, 1:-2, 1:] \
        * maskV[1:-2, 1:-2, :-1])
    flux_top = update(flux_top, at[:, :, -1], 0.0)
    dv_mix = update(dv_mix, at[:, :, 1:], (flux_top[:, :, 1:] - flux_top[:, :, :-1]) \
        / dzt[np.newaxis, np.newaxis, 1:] * maskV[:, :, 1:])
    dv_mix = update(dv_mix, at[:, :, 0], flux_top[:, :, 0] / dzt[0] * maskV[:, :, 0])

    """
    diagnose dissipation by vertical friction of meridional momentum
    """
    diss = update(diss, at[1:-2, 1:-2, :-1], (v[1:-2, 1:-2, 1:, tau] - v[1:-2, 1:-2, :-1, tau]) \
        * flux_top[1:-2, 1:-2, :-1] / dzw[np.newaxis, np.newaxis, :-1])
    diss = update(diss, at[:, :, -1], 0.0)
    diss = numerics.vgrid_to_tgrid(diss, area_v, area_t)
    K_diss_v += diss

    return du_mix, dv_mix, K_diss_v


@veros_kernel
def implicit_vert_friction(du_mix, dv_mix, K_diss_v, u, v, kbot, kappaM, tau, taup1,
                           dxt, dxu, area_v, area_t, dt_mom, dzt, dzw, maskU, maskV):
    """
    vertical friction
    dissipation is calculated and added to K_diss_v
    """
    nz = maskU.shape[2]
    diss = np.zeros_like(maskU)
    a_tri = np.zeros_like(maskU[1:-2, 1:-2])
    b_tri = np.zeros_like(maskU[1:-2, 1:-2])
    c_tri = np.zeros_like(maskU[1:-2, 1:-2])
    d_tri = np.zeros_like(maskU[1:-2, 1:-2])
    delta = np.zeros_like(maskU[1:-2, 1:-2])
    flux_top = np.zeros_like(maskU)

    """
    implicit vertical friction of zonal momentum
    """
    kss = np.maximum(kbot[1:-2, 1:-2], kbot[2:-1, 1:-2])
    _, water_mask, edge_mask = utilities.create_water_masks(kss, nz)

    fxa = 0.5 * (kappaM[1:-2, 1:-2, :-1] + kappaM[2:-1, 1:-2, :-1])
    delta = update(delta, at[:, :, :-1], dt_mom / dzw[:-1] * fxa * maskU[1:-2, 1:-2, 1:] * maskU[1:-2, 1:-2, :-1])
    a_tri = update(a_tri, at[:, :, 1:], -delta[:, :, :-1] / dzt[np.newaxis, np.newaxis, 1:])
    b_tri = update(b_tri, at[:, :, 1:], 1 + delta[:, :, :-1] / dzt[np.newaxis, np.newaxis, 1:])
    b_tri = update_add(b_tri, at[:, :, 1:-1], delta[:, :, 1:-1] / dzt[np.newaxis, np.newaxis, 1:-1])
    b_tri_edge = 1 + delta / dzt[np.newaxis, np.newaxis, :]
    c_tri = update(c_tri, at[...], -delta / dzt[np.newaxis, np.newaxis, :])
    d_tri = update(d_tri, at[...], u[1:-2, 1:-2, :, tau])

    res = utilities.solve_implicit(a_tri, b_tri, c_tri, d_tri, water_mask, b_edge=b_tri_edge, edge_mask=edge_mask)
    u = update(u, at[1:-2, 1:-2, :, taup1], np.where(water_mask, res, u[1:-2, 1:-2, :, taup1]))
    du_mix = update(du_mix, at[1:-2, 1:-2], (u[1:-2, 1:-2, :, taup1] - u[1:-2, 1:-2, :, tau]) / dt_mom)

    """
    diagnose dissipation by vertical friction of zonal momentum
    """
    fxa = 0.5 * (kappaM[1:-2, 1:-2, :-1] + kappaM[2:-1, 1:-2, :-1])
    flux_top = update(flux_top, at[1:-2, 1:-2, :-1], fxa * (u[1:-2, 1:-2, 1:, taup1] - u[1:-2, 1:-2, :-1, taup1]) \
        / dzw[:-1] * maskU[1:-2, 1:-2, 1:] * maskU[1:-2, 1:-2, :-1])
    diss = update(diss, at[1:-2, 1:-2, :-1], (u[1:-2, 1:-2, 1:, tau] - u[1:-2, 1:-2, :-1, tau]) \
        * flux_top[1:-2, 1:-2, :-1] / dzw[:-1])
    diss = update(diss, at[:, :, -1], 0.0)
    diss = numerics.ugrid_to_tgrid(diss, dxt, dxu)
    K_diss_v += diss

    """
    implicit vertical friction of meridional momentum
    """
    kss = np.maximum(kbot[1:-2, 1:-2], kbot[1:-2, 2:-1])
    _, water_mask, edge_mask = utilities.create_water_masks(kss, nz)

    fxa = 0.5 * (kappaM[1:-2, 1:-2, :-1] + kappaM[1:-2, 2:-1, :-1])
    delta = update(delta, at[:, :, :-1], dt_mom / dzw[np.newaxis, np.newaxis, :-1] * \
        fxa * maskV[1:-2, 1:-2, 1:] * maskV[1:-2, 1:-2, :-1])
    a_tri = update(a_tri, at[:, :, 1:], -delta[:, :, :-1] / dzt[np.newaxis, np.newaxis, 1:])
    b_tri = update(b_tri, at[:, :, 1:], 1 + delta[:, :, :-1] / dzt[np.newaxis, np.newaxis, 1:])
    b_tri = update_add(b_tri, at[:, :, 1:-1], delta[:, :, 1:-1] / dzt[np.newaxis, np.newaxis, 1:-1])
    b_tri_edge = 1 + delta / dzt[np.newaxis, np.newaxis, :]
    c_tri = update(c_tri, at[:, :, :-1], -delta[:, :, :-1] / dzt[np.newaxis, np.newaxis, :-1])
    c_tri = update(c_tri, at[:, :, -1], 0.)
    d_tri = update(d_tri, at[...], v[1:-2, 1:-2, :, tau])

    res = utilities.solve_implicit(a_tri, b_tri, c_tri, d_tri, water_mask, b_edge=b_tri_edge, edge_mask=edge_mask)
    v = update(v, at[1:-2, 1:-2, :, taup1], np.where(water_mask, res, v[1:-2, 1:-2, :, taup1]))
    dv_mix = update(dv_mix, at[1:-2, 1:-2], (v[1:-2, 1:-2, :, taup1] - v[1:-2, 1:-2, :, tau]) / dt_mom)

    """
    diagnose dissipation by vertical friction of meridional momentum
    """
    fxa = 0.5 * (kappaM[1:-2, 1:-2, :-1] + kappaM[1:-2, 2:-1, :-1])
    flux_top = update(flux_top, at[1:-2, 1:-2, :-1], fxa * (v[1:-2, 1:-2, 1:, taup1] - v[1:-2, 1:-2, :-1, taup1]) \
        / dzw[:-1] * maskV[1:-2, 1:-2, 1:] * maskV[1:-2, 1:-2, :-1])
    diss = update(diss, at[1:-2, 1:-2, :-1], (v[1:-2, 1:-2, 1:, tau] - v[1:-2, 1:-2, :-1, tau]) \
        * flux_top[1:-2, 1:-2, :-1] / dzw[:-1])
    diss = update(diss, at[:, :, -1], 0.0)
    diss = numerics.vgrid_to_tgrid(diss, area_v, area_t)
    K_diss_v += diss

    return u, v, du_mix, dv_mix, K_diss_v


@veros_kernel
def rayleigh_friction(du_mix, dv_mix, K_diss_bot, maskU, maskV, u, v, tau,
                      kbot, nz, dzw, dxt, dxu, r_ray, area_v, area_t,
                      enable_conserve_energy):
    """
    interior Rayleigh friction
    dissipation is calculated and added to K_diss_bot
    """
    du_mix = update_add(du_mix, at[...], -maskU * r_ray * u[..., tau])
    if enable_conserve_energy:
        diss = maskU * r_ray * u[..., tau]**2
        K_diss_bot = update_add(K_diss_bot, at[...], numerics.calc_diss_u(diss, kbot, nz, dzw, dxt, dxu))
    dv_mix = update_add(dv_mix, at[...], -maskV * r_ray * v[..., tau])

    if enable_conserve_energy:
        diss = maskV * r_ray * v[..., tau]**2
        K_diss_bot = update_add(K_diss_bot, at[...], numerics.calc_diss_v(diss, kbot, nz, dzw, area_v, area_t))

    return du_mix, dv_mix, K_diss_bot


@veros_kernel
def linear_bottom_friction(u, v, du_mix, dv_mix, K_diss_bot, kbot, nz, maskU, maskV,
                           r_bot, r_bot_var_u, r_bot_var_v, tau, dzw,
                           grav, rho_0, flux_east,
                           flux_north, dxt, dxu, dyt, cost,
                           area_v, area_t, enable_bottom_friction_var,
                           enable_conserve_energy):
    """
    linear bottom friction
    dissipation is calculated and added to K_diss_bot
    """
    if enable_bottom_friction_var:
        """
        with spatially varying coefficient
        """
        k = np.maximum(kbot[1:-2, 2:-2], kbot[2:-1, 2:-2]) - 1
        mask = np.arange(nz) == k[:, :, np.newaxis]
        du_mix = update_add(du_mix, at[1:-2, 2:-2], -(maskU[1:-2, 2:-2] * r_bot_var_u[1:-2, 2:-2, np.newaxis]) \
            * u[1:-2, 2:-2, :, tau] * mask)
        if enable_conserve_energy:
            diss = np.zeros_like(maskU)
            diss = update(diss, at[1:-2, 2:-2], maskU[1:-2, 2:-2] * r_bot_var_u[1:-2, 2:-2, np.newaxis] \
                * u[1:-2, 2:-2, :, tau]**2 * mask)
            K_diss_bot = update_add(K_diss_bot, at[...], numerics.calc_diss_u(diss, kbot, nz, dzw, dxt, dxu))

        k = np.maximum(kbot[2:-2, 2:-1], kbot[2:-2, 1:-2]) - 1
        mask = np.arange(nz) == k[:, :, np.newaxis]
        dv_mix = update_add(dv_mix, at[2:-2, 1:-2], -(maskV[2:-2, 1:-2] * r_bot_var_v[2:-2, 1:-2, np.newaxis]) \
            * v[2:-2, 1:-2, :, tau] * mask)
        if enable_conserve_energy:
            diss = np.zeros_like(maskV)
            diss = update(diss, at[2:-2, 1:-2], maskV[2:-2, 1:-2] * r_bot_var_v[2:-2, 1:-2, np.newaxis] \
                * v[2:-2, 1:-2, :, tau]**2 * mask)
            K_diss_bot = update_add(K_diss_bot, at[...], numerics.calc_diss_v(diss, kbot, nz, dzw, area_v, area_t))
    else:
        """
        with constant coefficient
        """
        k = np.maximum(kbot[1:-2, 2:-2], kbot[2:-1, 2:-2]) - 1
        mask = np.arange(nz) == k[:, :, np.newaxis]
        du_mix = update_add(du_mix, at[1:-2, 2:-2], -maskU[1:-2, 2:-2] * r_bot * u[1:-2, 2:-2, :, tau] * mask)
        if enable_conserve_energy:
            diss = np.zeros_like(maskU)
            diss = update(diss, at[1:-2, 2:-2], maskU[1:-2, 2:-2] * r_bot * u[1:-2, 2:-2, :, tau]**2 * mask)
            K_diss_bot = update_add(K_diss_bot, at[...], numerics.calc_diss_u(diss, kbot, nz, dzw, dxt, dxu))

        k = np.maximum(kbot[2:-2, 2:-1], kbot[2:-2, 1:-2]) - 1
        mask = np.arange(nz) == k[:, :, np.newaxis]
        dv_mix = update_add(dv_mix, at[2:-2, 1:-2], -maskV[2:-2, 1:-2] * r_bot * v[2:-2, 1:-2, :, tau] * mask)
        if enable_conserve_energy:
            diss = np.zeros_like(maskV)
            diss = update(diss, at[2:-2, 1:-2], maskV[2:-2, 1:-2] * r_bot * v[2:-2, 1:-2, :, tau]**2 * mask)
            K_diss_bot = update_add(K_diss_bot, at[...], numerics.calc_diss_v(diss, kbot, nz, dzw, area_v, area_t))

    return du_mix, dv_mix, K_diss_bot

@veros_kernel
def quadratic_bottom_friction(du_mix, dv_mix, K_diss_bot, u, v, r_quad_bot, dzt,
                              dzw, grav, rho_0, flux_east,
                              flux_north, dxt, dxu, dyt, cost, kbot, maskU, maskV, nz, tau,
                              area_v, area_t, enable_conserve_energy):
    """
    quadratic bottom friction
    dissipation is calculated and added to K_diss_bot
    """
    # we might want to account for EKE in the drag, also a tidal residual
    k = np.maximum(kbot[1:-2, 2:-2], kbot[2:-1, 2:-2]) - 1
    mask = k[..., np.newaxis] == np.arange(nz)[np.newaxis, np.newaxis, :]
    fxa = maskV[1:-2, 2:-2, :] * v[1:-2, 2:-2, :, tau]**2 \
        + maskV[1:-2, 1:-3, :] * v[1:-2, 1:-3, :, tau]**2 \
        + maskV[2:-1, 2:-2, :] * v[2:-1, 2:-2, :, tau]**2 \
        + maskV[2:-1, 1:-3, :] * v[2:-1, 1:-3, :, tau]**2
    fxa = np.sqrt(u[1:-2, 2:-2, :, tau]**2 + 0.25 * fxa)
    aloc = maskU[1:-2, 2:-2, :] * r_quad_bot * u[1:-2, 2:-2, :, tau] \
        * fxa / dzt[np.newaxis, np.newaxis, :] * mask
    du_mix = update_add(du_mix, at[1:-2, 2:-2, :], -aloc)

    if enable_conserve_energy:
        diss = np.zeros_like(maskU)
        diss = update(diss, at[1:-2, 2:-2, :], aloc * u[1:-2, 2:-2, :, tau])
        K_diss_bot = update_add(K_diss_bot, at[...], numerics.calc_diss_u(diss, kbot, nz, dzw, dxt, dxu))

    k = np.maximum(kbot[2:-2, 1:-2], kbot[2:-2, 2:-1]) - 1
    mask = k[..., np.newaxis] == np.arange(nz)[np.newaxis, np.newaxis, :]
    fxa = maskU[2:-2, 1:-2, :] * u[2:-2, 1:-2, :, tau]**2 \
        + maskU[1:-3, 1:-2, :] * u[1:-3, 1:-2, :, tau]**2 \
        + maskU[2:-2, 2:-1, :] * u[2:-2, 2:-1, :, tau]**2 \
        + maskU[1:-3, 2:-1, :] * u[1:-3, 2:-1, :, tau]**2
    fxa = np.sqrt(v[2:-2, 1:-2, :, tau]**2 + 0.25 * fxa)
    aloc = maskV[2:-2, 1:-2, :] * r_quad_bot * v[2:-2, 1:-2, :, tau] \
        * fxa / dzt[np.newaxis, np.newaxis, :] * mask
    dv_mix = update_add(dv_mix, at[2:-2, 1:-2, :], -aloc)

    if enable_conserve_energy:
        diss = np.zeros_like(maskV)
        diss = update(diss, at[2:-2, 1:-2, :], aloc * v[2:-2, 1:-2, :, tau])
        K_diss_bot = update_add(K_diss_bot, at[...], numerics.calc_diss_v(diss, kbot, nz, dzw, area_v, area_t))

    return du_mix, dv_mix, K_diss_bot


@veros_kernel
def harmonic_friction(du_mix, dv_mix, K_diss_h, cost, cosu, A_h, u, v, tau,
                      dxt, dxu, dyt, dyu, dzw, maskU, maskV, kbot, nz, area_v, area_t,
                      enable_hor_friction_cos_scaling, enable_noslip_lateral,
                      hor_friction_cosPower, enable_conserve_energy, grav, rho_0):
    """
    horizontal harmonic friction
    dissipation is calculated and added to K_diss_h
    """
    diss = np.zeros_like(maskU)
    flux_east = np.zeros_like(maskU)
    flux_north = np.zeros_like(maskV)

    """
    Zonal velocity
    """
    if enable_hor_friction_cos_scaling:
        fxa = cost**hor_friction_cosPower
        flux_east = update(flux_east, at[:-1], A_h * fxa[np.newaxis, :, np.newaxis] * (u[1:, :, :, tau] - u[:-1, :, :, tau]) \
            / (cost * dxt[1:, np.newaxis])[:, :, np.newaxis] * maskU[1:] * maskU[:-1])
        fxa = cosu**hor_friction_cosPower
        flux_north = update(flux_north, at[:, :-1], A_h * fxa[np.newaxis, :-1, np.newaxis] * (u[:, 1:, :, tau] - u[:, :-1, :, tau]) \
            / dyu[np.newaxis, :-1, np.newaxis] * maskU[:, 1:] * maskU[:, :-1] * cosu[np.newaxis, :-1, np.newaxis])
        if enable_noslip_lateral:
            flux_north = update_add(flux_north, at[:, :-1], 2 * A_h * fxa[np.newaxis, :-1, np.newaxis] * (u[:, 1:, :, tau]) \
                / dyu[np.newaxis, :-1, np.newaxis] * maskU[:, 1:] * (1 - maskU[:, :-1]) * cosu[np.newaxis, :-1, np.newaxis]\
                - 2 * A_h * fxa[np.newaxis, :-1, np.newaxis] * (u[:, :-1, :, tau]) \
                / dyu[np.newaxis, :-1, np.newaxis] * (1 - maskU[:, 1:]) * maskU[:, :-1] * cosu[np.newaxis, :-1, np.newaxis])
    else:
        flux_east = update(flux_east, at[:-1, :, :], A_h * (u[1:, :, :, tau] - u[:-1, :, :, tau]) \
            / (cost * dxt[1:, np.newaxis])[:, :, np.newaxis] * maskU[1:] * maskU[:-1])
        flux_north = update(flux_north, at[:, :-1, :], A_h * (u[:, 1:, :, tau] - u[:, :-1, :, tau]) \
            / dyu[np.newaxis, :-1, np.newaxis] * maskU[:, 1:] * maskU[:, :-1] * cosu[np.newaxis, :-1, np.newaxis])
        if enable_noslip_lateral:
            flux_north = update_add(flux_north, at[:, :-1], 2 * A_h * u[:, 1:, :, tau] / dyu[np.newaxis, :-1, np.newaxis] \
                * maskU[:, 1:] * (1 - maskU[:, :-1]) * cosu[np.newaxis, :-1, np.newaxis]\
                - 2 * A_h * u[:, :-1, :, tau] / dyu[np.newaxis, :-1, np.newaxis] \
                * (1 - maskU[:, 1:]) * maskU[:, :-1] * cosu[np.newaxis, :-1, np.newaxis])

    flux_east = update(flux_east, at[-1, :, :], 0.)
    flux_north = update(flux_north, at[:, -1, :], 0.)

    """
    update tendency
    """
    du_mix = update_add(du_mix, at[2:-2, 2:-2, :], maskU[2:-2, 2:-2] * ((flux_east[2:-2, 2:-2] - flux_east[1:-3, 2:-2])
                                                  / (cost[2:-2] * dxu[2:-2, np.newaxis])[:, :, np.newaxis]
                                                  + (flux_north[2:-2, 2:-2] - flux_north[2:-2, 1:-3])
                                                  / (cost[2:-2] * dyt[2:-2])[np.newaxis, :, np.newaxis]))

    if enable_conserve_energy:
        """
        diagnose dissipation by lateral friction
        """
        diss = update(diss, at[1:-2, 2:-2], 0.5 * ((u[2:-1, 2:-2, :, tau] - u[1:-2, 2:-2, :, tau]) * flux_east[1:-2, 2:-2]
                                  + (u[1:-2, 2:-2, :, tau] - u[:-3, 2:-2, :, tau]) * flux_east[:-3, 2:-2]) \
            / (cost[2:-2] * dxu[1:-2, np.newaxis])[:, :, np.newaxis]\
            + 0.5 * ((u[1:-2, 3:-1, :, tau] - u[1:-2, 2:-2, :, tau]) * flux_north[1:-2, 2:-2]
                     + (u[1:-2, 2:-2, :, tau] - u[1:-2, 1:-3, :, tau]) * flux_north[1:-2, 1:-3]) \
            / (cost[2:-2] * dyt[2:-2])[np.newaxis, :, np.newaxis])
        K_diss_h = update(K_diss_h, at[...], 0.)
        K_diss_h = update_add(K_diss_h, at[...], numerics.calc_diss_u(diss, kbot, nz, dzw, dxt, dxu))

    """
    Meridional velocity
    """
    if enable_hor_friction_cos_scaling:
        flux_east = update(flux_east, at[:-1], A_h * cosu[np.newaxis, :, np.newaxis] ** hor_friction_cosPower \
            * (v[1:, :, :, tau] - v[:-1, :, :, tau]) \
            / (cosu * dxu[:-1, np.newaxis])[:, :, np.newaxis] * maskV[1:] * maskV[:-1])
        if enable_noslip_lateral:
            flux_east = update_add(flux_east, at[:-1], 2 * A_h * fxa[np.newaxis, :, np.newaxis] * v[1:, :, :, tau] \
                / (cosu * dxu[:-1, np.newaxis])[:, :, np.newaxis] * maskV[1:] * (1 - maskV[:-1]) \
                - 2 * A_h * fxa[np.newaxis, :, np.newaxis] * v[:-1, :, :, tau] \
                / (cosu * dxu[:-1, np.newaxis])[:, :, np.newaxis] * (1 - maskV[1:]) * maskV[:-1])

        flux_north = update(flux_north, at[:, :-1], A_h * cost[np.newaxis, 1:, np.newaxis] ** hor_friction_cosPower \
            * (v[:, 1:, :, tau] - v[:, :-1, :, tau]) \
            / dyt[np.newaxis, 1:, np.newaxis] * cost[np.newaxis, 1:, np.newaxis] * maskV[:, :-1] * maskV[:, 1:])
    else:
        flux_east = update(flux_east, at[:-1], A_h * (v[1:, :, :, tau] - v[:-1, :, :, tau]) \
            / (cosu * dxu[:-1, np.newaxis])[:, :, np.newaxis] * maskV[1:] * maskV[:-1])
        if enable_noslip_lateral:
            flux_east = update_add(flux_east, at[:-1], 2 * A_h * v[1:, :, :, tau] / (cosu * dxu[:-1, np.newaxis])[:, :, np.newaxis] \
                * maskV[1:] * (1 - maskV[:-1]) \
                - 2 * A_h * v[:-1, :, :, tau] / (cosu * dxu[:-1, np.newaxis])[:, :, np.newaxis] \
                * (1 - maskV[1:]) * maskV[:-1])
        flux_north = update(flux_north, at[:, :-1], A_h * (v[:, 1:, :, tau] - v[:, :-1, :, tau]) \
            / dyt[np.newaxis, 1:, np.newaxis] * cost[np.newaxis, 1:, np.newaxis] * maskV[:, :-1] * maskV[:, 1:])
    flux_east = update(flux_east, at[-1, :, :], 0.)
    flux_north = update(flux_north, at[:, -1, :], 0.)

    """
    update tendency
    """
    dv_mix = update_add(dv_mix, at[2:-2, 2:-2], maskV[2:-2, 2:-2] * ((flux_east[2:-2, 2:-2] - flux_east[1:-3, 2:-2])
                                               / (cosu[2:-2] * dxt[2:-2, np.newaxis])[:, :, np.newaxis]
                                               + (flux_north[2:-2, 2:-2] - flux_north[2:-2, 1:-3])
                                               / (dyu[2:-2] * cosu[2:-2])[np.newaxis, :, np.newaxis]))

    if enable_conserve_energy:
        """
        diagnose dissipation by lateral friction
        """
        diss = update(diss, at[2:-2, 1:-2], 0.5 * ((v[3:-1, 1:-2, :, tau] - v[2:-2, 1:-2, :, tau]) * flux_east[2:-2, 1:-2]
                                  + (v[2:-2, 1:-2, :, tau] - v[1:-3, 1:-2, :, tau]) * flux_east[1:-3, 1:-2]) \
            / (cosu[1:-2] * dxt[2:-2, np.newaxis])[:, :, np.newaxis] \
            + 0.5 * ((v[2:-2, 2:-1, :, tau] - v[2:-2, 1:-2, :, tau]) * flux_north[2:-2, 1:-2]
                     + (v[2:-2, 1:-2, :, tau] - v[2:-2, :-3, :, tau]) * flux_north[2:-2, :-3]) \
            / (cosu[1:-2] * dyu[1:-2])[np.newaxis, :, np.newaxis])
        K_diss_h = update_add(K_diss_h, at[...], numerics.calc_diss_v(diss, kbot, nz, dzw, area_v, area_t))

    return du_mix, dv_mix, K_diss_h


@veros_kernel
def biharmonic_friction(du_mix, dv_mix, K_diss_h, A_hbi, u, v, tau, area_v, area_t,
                        cost, cosu, dxt, dxu, dyt, dyu, dzw, maskU, maskV, enable_cyclic_x,
                        kbot, nz, enable_noslip_lateral, enable_conserve_energy):
    """
    horizontal biharmonic friction
    dissipation is calculated and added to K_diss_h
    """
    flux_east = np.zeros_like(maskU)
    flux_north = np.zeros_like(maskV)
    fxa = np.sqrt(abs(A_hbi))

    """
    Zonal velocity
    """
    flux_east = update(flux_east, at[:-1, :, :], fxa * (u[1:, :, :, tau] - u[:-1, :, :, tau]) \
        / (cost[np.newaxis, :, np.newaxis] * dxt[1:, np.newaxis, np.newaxis]) \
        * maskU[1:, :, :] * maskU[:-1, :, :])
    flux_north = update(flux_north, at[:, :-1, :], fxa * (u[:, 1:, :, tau] - u[:, :-1, :, tau]) \
        / dyu[np.newaxis, :-1, np.newaxis] * maskU[:, 1:, :] \
        * maskU[:, :-1, :] * cosu[np.newaxis, :-1, np.newaxis])
    if enable_noslip_lateral:
        flux_north = update_add(flux_north, at[:, :-1], 2 * fxa * u[:, 1:, :, tau] / dyu[np.newaxis, :-1, np.newaxis] \
            * maskU[:, 1:] * (1 - maskU[:, :-1]) * cosu[np.newaxis, :-1, np.newaxis]\
            - 2 * fxa * u[:, :-1, :, tau] / dyu[np.newaxis, :-1, np.newaxis] \
            * (1 - maskU[:, 1:]) * maskU[:, :-1] * cosu[np.newaxis, :-1, np.newaxis])
    flux_east = update(flux_east, at[-1, :, :], 0.)
    flux_north = update(flux_north, at[:, -1, :], 0.)

    del2 = np.zeros_like(maskU)
    del2 = update(del2, at[1:, 1:, :], (flux_east[1:, 1:, :] - flux_east[:-1, 1:, :]) \
        / (cost[np.newaxis, 1:, np.newaxis] * dxu[1:, np.newaxis, np.newaxis]) \
        + (flux_north[1:, 1:, :] - flux_north[1:, :-1, :]) \
        / (cost[np.newaxis, 1:, np.newaxis] * dyt[np.newaxis, 1:, np.newaxis]))

    flux_east = update(flux_east, at[:-1, :, :], fxa * (del2[1:, :, :] - del2[:-1, :, :]) \
        / (cost[np.newaxis, :, np.newaxis] * dxt[1:, np.newaxis, np.newaxis]) \
        * maskU[1:, :, :] * maskU[:-1, :, :])
    flux_north = update(flux_north, at[:, :-1, :], fxa * (del2[:, 1:, :] - del2[:, :-1, :]) \
        / dyu[np.newaxis, :-1, np.newaxis] * maskU[:, 1:, :] \
        * maskU[:, :-1, :] * cosu[np.newaxis, :-1, np.newaxis])
    if enable_noslip_lateral:
        flux_north = update_add(flux_north, at[:, :-1, :], 2 * fxa * del2[:, 1:, :] / dyu[np.newaxis, :-1, np.newaxis] \
            * maskU[:, 1:, :] * (1 - maskU[:, :-1, :]) * cosu[np.newaxis, :-1, np.newaxis] \
            - 2 * fxa * del2[:, :-1, :] / dyu[np.newaxis, :-1, np.newaxis] \
            * (1 - maskU[:, 1:, :]) * maskU[:, :-1, :] * cosu[np.newaxis, :-1, np.newaxis])
    flux_east = update(flux_east, at[-1, :, :], 0.)
    flux_north = update(flux_north, at[:, -1, :], 0.)

    """
    update tendency
    """
    du_mix = update_add(du_mix, at[2:-2, 2:-2, :], -maskU[2:-2, 2:-2, :] * ((flux_east[2:-2, 2:-2, :] - flux_east[1:-3, 2:-2, :])
                                                      / (cost[np.newaxis, 2:-2, np.newaxis] * dxu[2:-2, np.newaxis, np.newaxis])
                                                      + (flux_north[2:-2, 2:-2, :] - flux_north[2:-2, 1:-3, :])
                                                      / (cost[np.newaxis, 2:-2, np.newaxis] * dyt[np.newaxis, 2:-2, np.newaxis])))
    if enable_conserve_energy:
        """
        diagnose dissipation by lateral friction
        """
        flux_east = utilities.enforce_boundaries(flux_east, enable_cyclic_x)
        flux_north = utilities.enforce_boundaries(flux_north, enable_cyclic_x)
        diss = np.zeros_like(maskU)
        diss = update(diss, at[1:-2, 2:-2, :], -0.5 * ((u[2:-1, 2:-2, :, tau] - u[1:-2, 2:-2, :, tau]) * flux_east[1:-2, 2:-2, :]
                                      + (u[1:-2, 2:-2, :, tau] - u[:-3, 2:-2, :, tau]) * flux_east[:-3, 2:-2, :]) \
            / (cost[np.newaxis, 2:-2, np.newaxis] * dxu[1:-2, np.newaxis, np.newaxis])  \
            - 0.5 * ((u[1:-2, 3:-1, :, tau] - u[1:-2, 2:-2, :, tau]) * flux_north[1:-2, 2:-2, :]
                     + (u[1:-2, 2:-2, :, tau] - u[1:-2, 1:-3, :, tau]) * flux_north[1:-2, 1:-3, :]) \
            / (cost[np.newaxis, 2:-2, np.newaxis] * dyt[np.newaxis, 2:-2, np.newaxis]))
        K_diss_h = numerics.calc_diss_u(diss, kbot, nz, dzw, dxt, dxu)

    """
    Meridional velocity
    """
    flux_east = update(flux_east, at[:-1, :, :], fxa * (v[1:, :, :, tau] - v[:-1, :, :, tau]) \
        / (cosu[np.newaxis, :, np.newaxis] * dxu[:-1, np.newaxis, np.newaxis]) \
        * maskV[1:, :, :] * maskV[:-1, :, :])
    if enable_noslip_lateral:
        flux_east = update_add(flux_east, at[:-1, :, :], 2 * fxa * v[1:, :, :, tau] / (cosu[np.newaxis, :, np.newaxis] * dxu[:-1, np.newaxis, np.newaxis]) \
            * maskV[1:, :, :] * (1 - maskV[:-1, :, :]) \
            - 2 * fxa * v[:-1, :, :, tau] / (cosu[np.newaxis, :, np.newaxis] * dxu[:-1, np.newaxis, np.newaxis]) \
            * (1 - maskV[1:, :, :]) * maskV[:-1, :, :])
    flux_north = update(flux_north, at[:, :-1, :], fxa * (v[:, 1:, :, tau] - v[:, :-1, :, tau]) \
        / dyt[np.newaxis, 1:, np.newaxis] * cost[np.newaxis, 1:, np.newaxis] \
        * maskV[:, :-1, :] * maskV[:, 1:, :])
    flux_east = update(flux_east, at[-1, :, :], 0.)
    flux_north = update(flux_north, at[:, -1, :], 0.)

    del2 = update(del2, at[1:, 1:, :], (flux_east[1:, 1:, :] - flux_east[:-1, 1:, :]) \
        / (cosu[np.newaxis, 1:, np.newaxis] * dxt[1:, np.newaxis, np.newaxis])  \
        + (flux_north[1:, 1:, :] - flux_north[1:, :-1, :]) \
        / (dyu[np.newaxis, 1:, np.newaxis] * cosu[np.newaxis, 1:, np.newaxis]))

    flux_east = update(flux_east, at[:-1, :, :], fxa * (del2[1:, :, :] - del2[:-1, :, :]) \
        / (cosu[np.newaxis, :, np.newaxis] * dxu[:-1, np.newaxis, np.newaxis]) \
        * maskV[1:, :, :] * maskV[:-1, :, :])
    if enable_noslip_lateral:
        flux_east = update_add(flux_east, at[:-1, :, :], 2 * fxa * del2[1:, :, :] / (cosu[np.newaxis, :, np.newaxis] * dxu[:-1, np.newaxis, np.newaxis]) \
            * maskV[1:, :, :] * (1 - maskV[:-1, :, :]) \
            - 2 * fxa * del2[:-1, :, :] / (cosu[np.newaxis, :, np.newaxis] * dxu[:-1, np.newaxis, np.newaxis]) \
            * (1 - maskV[1:, :, :]) * maskV[:-1, :, :])
    flux_north = update(flux_north, at[:, :-1, :], fxa * (del2[:, 1:, :] - del2[:, :-1, :]) \
        / dyt[np.newaxis, 1:, np.newaxis] * cost[np.newaxis, 1:, np.newaxis] \
        * maskV[:, :-1, :] * maskV[:, 1:, :])
    flux_east = update(flux_east, at[-1, :, :], 0.)
    flux_north = update(flux_north, at[:, -1, :], 0.)

    """
    update tendency
    """
    dv_mix = update_add(dv_mix, at[2:-2, 2:-2, :], -maskV[2:-2, 2:-2, :] * ((flux_east[2:-2, 2:-2, :] - flux_east[1:-3, 2:-2, :])
                                                      / (cosu[np.newaxis, 2:-2, np.newaxis] * dxt[2:-2, np.newaxis, np.newaxis])
                                                      + (flux_north[2:-2, 2:-2, :] - flux_north[2:-2, 1:-3, :])
                                                      / (dyu[np.newaxis, 2:-2, np.newaxis] * cosu[np.newaxis, 2:-2, np.newaxis])))

    if enable_conserve_energy:
        """
        diagnose dissipation by lateral friction
        """
        flux_east = utilities.enforce_boundaries(flux_east, enable_cyclic_x)
        flux_north = utilities.enforce_boundaries(flux_north, enable_cyclic_x)
        diss = update(diss, at[2:-2, 1:-2, :], -0.5 * ((v[3:-1, 1:-2, :, tau] - v[2:-2, 1:-2, :, tau]) * flux_east[2:-2, 1:-2, :]
                                      + (v[2:-2, 1:-2, :, tau] - v[1:-3, 1:-2, :, tau]) * flux_east[1:-3, 1:-2, :]) \
            / (cosu[np.newaxis, 1:-2, np.newaxis] * dxt[2:-2, np.newaxis, np.newaxis]) \
            - 0.5 * ((v[2:-2, 2:-1, :, tau] - v[2:-2, 1:-2, :, tau]) * flux_north[2:-2, 1:-2, :]
                     + (v[2:-2, 1:-2, :, tau] - v[2:-2, :-3, :, tau]) * flux_north[2:-2, :-3, :]) \
            / (cosu[np.newaxis, 1:-2, np.newaxis] * dyu[np.newaxis, 1:-2, np.newaxis]))
        K_diss_h = update_add(K_diss_h, at[...], numerics.calc_diss_v(diss, kbot, nz, dzw, area_v, area_t))

    return du_mix, dv_mix, K_diss_h


@veros_kernel
def momentum_sources(du_mix, dv_mix, K_diss_bot, u, v, u_source, v_source, area_v, area_t,
                     tau, maskU, maskV, kbot, nz, dzw, dxt, dxu, enable_conserve_energy):
    """
    other momentum sources
    dissipation is calculated and added to K_diss_bot
    """
    du_mix = update_add(du_mix, at[...], maskU * u_source)
    if enable_conserve_energy:
        diss = -maskU * u[..., tau] * u_source
        K_diss_bot = update_add(K_diss_bot, at[...], numerics.calc_diss_u(diss, kbot, nz, dzw, dxt, dxu))
    dv_mix = update_add(dv_mix, at[...], maskV * v_source)
    if enable_conserve_energy:
        diss = -maskV * v[..., tau] * v_source
        K_diss_bot = update_add(K_diss_bot, at[...], numerics.calc_diss_v(diss, kbot, nz, dzw, area_v, area_t))

    return du_mix, dv_mix, K_diss_bot


@veros_routine
def friction(vs):
    """
    vertical friction
    """
    K_diss_v = np.zeros_like(vs.K_diss_v)
    if vs.enable_implicit_vert_friction:
        vs = implicit_vert_friction.run_with_state(vs)
    if vs.enable_explicit_vert_friction:
        vs = explicit_vert_friction.run_with_state(vs)

    """
    TEM formalism for eddy-driven velocity
    """
    if vs.enable_TEM_friction:
        du_mix, dv_mix, K_diss_gm, u, v = run_kernel(isoneutral.isoneutral_friction, vs,
                                                     du_mix=du_mix, dv_mix=dv_mix)
    else:
        K_diss_gm = 0

    """
    horizontal friction
    """
    if vs.enable_hor_friction:
        vs = harmonic_friction.run_with_state(vs,
                                              du_mix=du_mix, dv_mix=dv_mix)
    if vs.enable_biharmonic_friction:
        vs = biharmonic_friction.run_with_state(vs,
                                              du_mix=du_mix, dv_mix=dv_mix)

    """
    Rayleigh and bottom friction
    """
    K_diss_bot = update(vs.K_diss_bot, at[...], 0.0)
    if vs.enable_ray_friction:
        vs = rayleigh_friction.run_with_state(vs,
                                                du_mix=du_mix, dv_mix=dv_mix)
    if vs.enable_bottom_friction:
        if vs.enable_bottom_friction_var:
            r_bot_var_u, r_bot_var_v = vs.r_bot_var_u, vs.r_bot_var_v
        else:
            r_bot_var_u = r_bot_var_v = 0
        vs = linear_bottom_friction.run_with_state(vs,
                                                du_mix=du_mix, dv_mix=dv_mix,
                                                r_bot_var_u=r_bot_var_u, r_bot_var_v=r_bot_var_v)
    if vs.enable_quadratic_bottom_friction:
        vs = quadratic_bottom_friction.run_with_state(vs,
                                                du_mix=du_mix, dv_mix=dv_mix)

    """
    add user defined forcing
    """
    if vs.enable_momentum_sources:
        vs = momentum_sources.run_with_state(vs,
                                                du_mix=du_mix, dv_mix=dv_mix,
                                                K_diss_bot=K_diss_bot)

    return dict(
        u=u, v=v,
        du_mix=du_mix,
        dv_mix=dv_mix,
        K_diss_h=K_diss_h,
        K_diss_v=K_diss_v,
        K_diss_gm=K_diss_gm,
        K_diss_bot=K_diss_bot
    )
