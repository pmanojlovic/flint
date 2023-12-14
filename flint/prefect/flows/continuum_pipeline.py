"""A prefect based pipeline that:
- will perform bandpass calibration with PKS B1934-638 data, or from a derived sky-model
- copy and apply to science field
- image and self-calibration the science fields
- run aegean source finding
"""
from argparse import ArgumentParser
from pathlib import Path
from typing import Any, Collection, Dict, List, Optional, Union

from prefect import flow, task, unmapped

from flint.bandpass import extract_correct_bandpass_pointing, plot_solutions
from flint.calibrate.aocalibrate import (
    ApplySolutions,
    CalibrateCommand,
    create_apply_solutions_cmd,
    create_calibrate_cmd,
    find_existing_solutions,
    flag_aosolutions,
    select_aosolution_for_ms,
)
from flint.coadd.linmos import LinmosCMD, linmos_images
from flint.convol import BeamShape, convolve_images, get_common_beam
from flint.flagging import flag_ms_aoflagger
from flint.imager.wsclean import WSCleanCMD, wsclean_imager
from flint.logging import logger
from flint.ms import MS, preprocess_askap_ms, split_by_field
from flint.naming import get_sbid_from_path, processed_ms_format
from flint.prefect.clusters import get_dask_runner
from flint.selfcal.casa import gaincal_applycal_ms
from flint.source_finding.aegean import AegeanOutputs, run_bane_and_aegean
from flint.utils import zip_folder
from flint.validation import create_validation_plot

task_extract_correct_bandpass_pointing = task(extract_correct_bandpass_pointing)
task_preprocess_askap_ms = task(preprocess_askap_ms)
task_flag_ms_aoflagger = task(flag_ms_aoflagger)
task_create_calibrate_cmd = task(create_calibrate_cmd)
task_split_by_field = task(split_by_field)
task_select_solution_for_ms = task(select_aosolution_for_ms)
task_create_apply_solutions_cmd = task(create_apply_solutions_cmd)


@task
def task_bandpass_create_apply_solutions_cmd(
    ms: MS, calibrate_cmd: CalibrateCommand, container: Path
):
    return create_apply_solutions_cmd(
        ms=ms, solutions_file=calibrate_cmd.solution_path, container=container
    )


@task
def task_run_bane_and_aegean(
    image: Union[WSCleanCMD, LinmosCMD], aegean_container: Path
) -> AegeanOutputs:
    if isinstance(image, WSCleanCMD):
        assert image.imageset is not None, "Image set attribute unset. "
        image_paths = image.imageset.image

        logger.info(f"Have extracted image: {image_paths}")

        # For the moment, will only source find on an MFS image
        image_paths = [image for image in image_paths if "-MFS-" in str(image)]
        assert (
            len(image_paths) == 1
        ), "More than one image found after filter for MFS only images. "
        # Get out the only path in the list.
        image_path = image_paths[0]
    elif isinstance(image, LinmosCMD):
        logger.info("Will be running aegean on a linmos image")

        image_path = image.image_fits
        assert image_path.exists(), f"Image path {image_path} does not exist"
    else:
        raise ValueError(f"Unexpected type, have received {type(image)} for {image=}. ")

    aegean_outputs = run_bane_and_aegean(
        image=image_path, aegean_container=aegean_container
    )

    return aegean_outputs


@task
def task_zip_ms(in_item: WSCleanCMD) -> Path:
    ms = in_item.ms

    zipped_ms = zip_folder(in_path=ms.path)

    return zipped_ms


@task
def task_gaincal_applycal_ms(
    wsclean_cmd: WSCleanCMD,
    round: int,
    update_gain_cal_options: Optional[Dict[str, Any]] = None,
    archive_input_ms: bool = False,
) -> MS:
    # TODO: This needs to be expanded to handle multiple MS
    ms = wsclean_cmd.ms

    if not isinstance(ms, MS):
        raise ValueError(
            f"Unsupported {type(ms)=} {ms=}. Likely multiple MS instances? This is not yet supported. "
        )

    return gaincal_applycal_ms(
        ms=ms,
        round=round,
        update_gain_cal_options=update_gain_cal_options,
        archive_input_ms=archive_input_ms,
    )


@task
def task_flatten_prefect_futures(in_futures: List[List[Any]]) -> List[Any]:
    """Will flatten a list of lists into a single list. This
    is useful for when a task-descorated function returns a list.


    Args:
        in_futures (List[List[Any]]): Input list of lists to flatten

    Returns:
        List[Any]: Flattened form of input
    """
    logger.info(f"Received {len(in_futures)} to flatten.")
    flatten_list = [item for sublist in in_futures for item in sublist]
    logger.info(f"Flattened list {len(flatten_list)}")

    return flatten_list


@task
def task_flag_solutions(calibrate_cmd: CalibrateCommand) -> CalibrateCommand:
    solution_path = calibrate_cmd.solution_path
    ms_path = calibrate_cmd.ms.path

    plot_dir = ms_path.parent / Path("preflagger")
    if not plot_dir.exists():
        try:
            logger.info(f"Attempting to create {plot_dir}")
            plot_dir.mkdir(parents=True)
        except FileExistsError:
            logger.warn(
                "Creating the directory failed. Likely already exists. Race conditions, me-hearty."
            )

    flagged_solutions_path = flag_aosolutions(
        solutions_path=solution_path, ref_ant=0, flag_cut=3, plot_dir=plot_dir
    )

    return calibrate_cmd.with_options(
        solution_path=flagged_solutions_path, preflagged=True
    )


@task
def task_extract_solution_path(calibrate_cmd: CalibrateCommand) -> Path:
    return calibrate_cmd.solution_path


@task
def task_plot_solutions(calibrate_cmd: CalibrateCommand) -> None:
    plot_solutions(solutions_path=calibrate_cmd.solution_path, ref_ant=None)


@task
def task_wsclean_imager(
    in_ms: Union[ApplySolutions, MS],
    wsclean_container: Path,
    update_wsclean_options: Optional[Dict[str, Any]] = None,
) -> WSCleanCMD:
    ms = in_ms if isinstance(in_ms, MS) else in_ms.ms

    logger.info(f"wsclean inager {ms=}")
    return wsclean_imager(
        ms=ms,
        wsclean_container=wsclean_container,
        update_wsclean_options=update_wsclean_options,
    )


@task
def task_get_common_beam(
    wsclean_cmds: Collection[WSCleanCMD], cutoff: float = 25
) -> BeamShape:
    images_to_consider: List[Path] = []

    for wsclean_cmd in wsclean_cmds:
        if wsclean_cmd.imageset is None:
            logger.warn(f"No imageset fo {wsclean_cmd.ms} found. Has imager finished?")
            continue
        images_to_consider.extend(wsclean_cmd.imageset.image)

    logger.info(
        f"Considering {len(images_to_consider)} images across {len(wsclean_cmds)} outputs. "
    )

    beam_shape = get_common_beam(image_paths=images_to_consider, cutoff=cutoff)

    return beam_shape


@task
def task_convolve_image(
    wsclean_cmd: WSCleanCMD, beam_shape: BeamShape, cutoff: float = 60
) -> Collection[Path]:
    assert (
        wsclean_cmd.imageset is not None
    ), f"{wsclean_cmd.ms} has no attached imageset."
    image_paths: Collection[Path] = wsclean_cmd.imageset.image

    logger.info(f"Will convolve {image_paths}")

    # experience has shown that astropy units do not always work correctly
    # in a multiprocessing / dask environment. The unit registery does not
    # seem to serialise correctly, and we can get weird arcsecond is not
    # compatiable with arcsecond type errors. Import here in an attempt
    # to minimise
    import astropy.units as u
    from astropy.io import fits
    from radio_beam import Beam

    # Print the beams out here for logging
    for image_path in image_paths:
        image_beam = Beam.from_fits_header(fits.getheader(str(image_path)))
        logger.info(
            f"{str(image_path.name)}: {image_beam.major.to(u.arcsecond)} {image_beam.minor.to(u.arcsecond)}  {image_beam.pa}"
        )

    return convolve_images(
        image_paths=image_paths, beam_shape=beam_shape, cutoff=cutoff
    )


@task
def task_linmos_images(
    images: Collection[Collection[Path]],
    container: Path,
    filter: str = "-MFS-",
    field_name: Optional[str] = None,
    suffix_str: str = "noselfcal",
    holofile: Optional[Path] = None,
    sbid: Optional[int] = None,
    parset_output_path: Optional[str] = None,
) -> LinmosCMD:
    # TODO: Need to flatten images
    # TODO: Need a better way of getting field names

    all_images = [img for beam_images in images for img in beam_images]
    logger.info(f"Number of images to examine {len(all_images)}")

    filter_images = [img for img in all_images if filter in str(img)]
    logger.info(f"Number of filtered images to linmos: {len(filter_images)}")

    candidate_image = filter_images[0]
    candidate_image_fields = processed_ms_format(in_name=candidate_image)

    if field_name is None:
        field_name = candidate_image_fields.field
        logger.info(f"Extracted {field_name=} from {candidate_image=}")

    if sbid is None:
        sbid = candidate_image_fields.sbid
        logger.info(f"Extracted {sbid=} from {candidate_image=}")

    base_name = f"SB{sbid}.{field_name}.{suffix_str}"

    out_dir = Path(filter_images[0].parent)
    out_name = out_dir / base_name
    logger.info(f"Base output image name will be: {out_name}")

    if parset_output_path is None:
        parset_output_path = f"{out_name.name}_parset.txt"

    parset_output_path = out_dir / Path(parset_output_path)
    logger.info(f"Parsert output path is {parset_output_path}")

    linmos_cmd = linmos_images(
        images=filter_images,
        parset_output_path=Path(parset_output_path),
        image_output_name=str(out_name),
        container=container,
        holofile=holofile,
    )

    return linmos_cmd

@task
def task_create_validation_plot(
    aegean_outputs: AegeanOutputs, reference_catalogue_directory: Path
) -> Path:
    output_figure_path = aegean_outputs.comp.with_suffix(".validation.png")

    logger.info(f"Will create {output_figure_path=}")

    return create_validation_plot(
        rms_image_path=aegean_outputs.rms,
        source_catalogue_path=aegean_outputs.comp,
        output_path=output_figure_path,
        reference_catalogue_directory=reference_catalogue_directory,
    )


@flow(name="Flint Continuum Pipeline")
def process_science_fields(
    science_path: Path,
    bandpass_path: Path,
    split_path: Path,
    flagger_container: Path,
    calibrate_container: Path,
    holofile: Optional[Path] = None,
    expected_ms: int = 36,
    wsclean_container: Optional[Path] = None,
    rounds: Optional[int] = 2,
    yandasoft_container: Optional[Path] = None,
    zip_ms: bool = False,
    run_aegean: bool = False,
    aegean_container: Optional[Path] = None,
    no_imaging: bool = False,
    reference_catalogue_directory: Optional[Path] = None,
) -> None:
    run_aegean = False if aegean_container is None else run_aegean
    run_validation = reference_catalogue_directory is not None

    assert (
        science_path.exists() and science_path.is_dir()
    ), f"{str(science_path)} does not exist or is not a folder. "
    science_mss = list(
        [MS.cast(ms_path) for ms_path in sorted(science_path.glob("*.ms"))]
    )
    assert (
        len(science_mss) == expected_ms
    ), f"Expected to find {expected_ms} in {str(science_path)}, found {len(science_mss)}."

    science_folder_name = science_path.name

    output_split_science_path = (
        Path(split_path / science_folder_name).absolute().resolve()
    )

    if not output_split_science_path.exists():
        logger.info(f"Creating {str(output_split_science_path)}")
        output_split_science_path.mkdir(parents=True)

    logger.info(f"Found the following raw measurement sets: {science_mss}")

    # TODO: This will likely need to be expanded should any
    # other calibration strategies get added
    # Scan the existing bandpass directory for the existing solutions
    calibrate_cmds = find_existing_solutions(
        bandpass_directory=bandpass_path,
        use_preflagged=True,
        use_smoothed=False
    )
    
    logger.info(f"Constructed the following {calibrate_cmds=}")

    split_science_mss = task_split_by_field.map(
        ms=science_mss, field=None, out_dir=unmapped(output_split_science_path)
    )

    # The following line will block until the science
    # fields are split out. Since there might be more
    # than a single field in an SBID, we should do this
    flat_science_mss = task_flatten_prefect_futures(split_science_mss)

    preprocess_science_mss = task_preprocess_askap_ms.map(
        ms=flat_science_mss,
        data_column=unmapped("DATA"),
        instrument_column=unmapped("INSTRUMENT_DATA"),
        overwrite=True,
    )
    flag_field_mss = task_flag_ms_aoflagger.map(
        ms=preprocess_science_mss, container=flagger_container, rounds=1
    )
    solutions_paths = task_select_solution_for_ms.map(
        calibrate_cmds=unmapped(calibrate_cmds), ms=flag_field_mss
    ) 
    apply_solutions_cmds = task_create_apply_solutions_cmd.map(
        ms=flag_field_mss,
        solutions_file=solutions_paths,
        container=calibrate_container,
    )
    
    if no_imaging:
        logger.info(f"No imaging will be performed, as requested bu {no_imaging=}")
        return

    if wsclean_container is None:
        logger.info("No wsclean container provided. Rerutning. ")
        return

    wsclean_init = {
        "size": 7144,
        "minuv_l": 235,
        "weight": "briggs -0.5",
        "auto_mask": 5,
        "multiscale": True,
        "local_rms_window": 55,
        "multiscale_scales": (0, 15, 30, 40, 50, 60, 70),
    }

    wsclean_cmds = task_wsclean_imager.map(
        in_ms=apply_solutions_cmds,
        wsclean_container=wsclean_container,
        update_wsclean_options=unmapped(wsclean_init),
    )
    if run_aegean:
        task_run_bane_and_aegean.map(
            image=wsclean_cmds, aegean_container=unmapped(aegean_container)
        )

    beam_shape = task_get_common_beam.submit(wsclean_cmds=wsclean_cmds, cutoff=150.0)
    conv_images = task_convolve_image.map(
        wsclean_cmd=wsclean_cmds, beam_shape=unmapped(beam_shape), cutoff=150.0
    )
    if yandasoft_container is not None:
        parset = task_linmos_images.submit(
            images=conv_images,
            container=yandasoft_container,
            suffix_str="noselfcal",
            holofile=holofile,
        )

        if run_aegean:
            aegean_outputs = task_run_bane_and_aegean.submit(
                image=parset, aegean_container=unmapped(aegean_container)
            )

            if run_validation:
                task_create_validation_plot.submit(
                    aegean_outputs=aegean_outputs,
                    reference_catalogue_directory=reference_catalogue_directory,
                )

    if rounds is None:
        logger.info("No self-calibration will be performed. Returning")
        return

    gain_cal_rounds = {
        1: {"solint": "1200s", "uvrange": ">235lambda", "nspw": 1},
        2: {"solint": "60s", "uvrange": ">235lambda", "nspw": 1},
        3: {"solint": "60s", "uvrange": ">235lambda", "nspw": 1},
        4: {"calmode": "ap", "solint": "360s", "uvrange": ">200lambda"},
    }
    wsclean_rounds = {
        1: {
            "size": 7144,
            "multiscale": True,
            "minuv_l": 235,
            "auto_mask": 5,
            "local_rms_window": 55,
            "multiscale_scales": (0, 15, 30, 40, 50, 60, 70),
        },
        2: {
            "size": 7144,
            "multiscale": True,
            "minuv_l": 235,
            "auto_mask": 4.0,
            "local_rms_window": 55,
            "multiscale_scales": (0, 15, 30, 40, 50, 60, 70),
        },
        3: {"multiscale": False, "minuv_l": 200, "auto_mask": 3.5},
        4: {
            "multiscale": False,
            "local_rms_window": 125,
            "minuv_l": 200,
            "auto_mask": 3.5,
        },
    }

    for round in range(1, rounds + 1):
        gain_cal_options = gain_cal_rounds.get(round, None)
        wsclean_options = wsclean_rounds.get(round, None)

        cal_mss = task_gaincal_applycal_ms.map(
            wsclean_cmd=wsclean_cmds,
            round=round,
            update_gain_cal_options=unmapped(gain_cal_options),
            archive_input_ms=zip_ms,
        )

        flag_mss = task_flag_ms_aoflagger.map(
            ms=cal_mss, container=flagger_container, rounds=1
        )
        wsclean_cmds = task_wsclean_imager.map(
            in_ms=flag_mss,
            wsclean_container=wsclean_container,
            update_wsclean_options=unmapped(wsclean_options),
        )

        # Do source finding on the last round of self-cal'ed images
        if round == rounds and run_aegean:
            task_run_bane_and_aegean.map(
                image=wsclean_cmds, aegean_container=unmapped(aegean_container)
            )

        beam_shape = task_get_common_beam.submit(
            wsclean_cmds=wsclean_cmds, cutoff=150.0
        )
        conv_images = task_convolve_image.map(
            wsclean_cmd=wsclean_cmds, beam_shape=unmapped(beam_shape), cutoff=150.0
        )
        if yandasoft_container is None:
            logger.info("No yandasoft container supplied, not linmosing. ")
            continue

        parset = task_linmos_images.submit(
            images=conv_images,
            container=yandasoft_container,
            suffix_str=f"round{round}",
            holofile=holofile,
        )

        if run_aegean:
            aegean_outputs = task_run_bane_and_aegean.submit(
                image=parset, aegean_container=unmapped(aegean_container)
            )

            if run_validation:
                task_create_validation_plot.submit(
                    aegean_outputs=aegean_outputs,
                    reference_catalogue_directory=reference_catalogue_directory,
                )

    # zip up the final measurement set, which is not included in the above loop
    if zip_ms:
        task_zip_ms.map(in_item=wsclean_cmds, wait_for=wsclean_cmds)


def setup_run_process_science_field(
    cluster_config: Union[str, Path],
    science_path: Path,
    bandpass_path: Path,
    split_path: Path,
    flagger_container: Path,
    calibrate_container: Path,
    holofile: Optional[Path] = None,
    expected_ms: int = 36,
    source_name_prefix: str = "B1934-638",
    wsclean_container: Optional[Path] = None,
    yandasoft_container: Optional[Path] = None,
    rounds: int = 2,
    zip_ms: bool = False,
    run_aegean: bool = False,
    aegean_container: Optional[Path] = None,
    no_imaging: bool = False,
    reference_catalogue_directory: Optional[Path] = None,
) -> None:
    assert bandpass_path.exists() and bandpass_path.is_dir(), f"{bandpass_path=} needs to exist and be a directory! "

    science_sbid = get_sbid_from_path(path=science_path)

    dask_task_runner = get_dask_runner(cluster=cluster_config)

    process_science_fields.with_options(
        name=f"Flint Continuum Pipeline - {science_sbid}", task_runner=dask_task_runner
    )(
        science_path=science_path,
        bandpass_path=bandpass_path,
        split_path=split_path,
        flagger_container=flagger_container,
        calibrate_container=calibrate_container,
        holofile=holofile,
        expected_ms=expected_ms,
        wsclean_container=wsclean_container,
        yandasoft_container=yandasoft_container,
        rounds=rounds,
        zip_ms=zip_ms,
        run_aegean=run_aegean,
        aegean_container=aegean_container,
        no_imaging=no_imaging,
        reference_catalogue_directory=reference_catalogue_directory,
    )


def get_parser() -> ArgumentParser:
    parser = ArgumentParser(description=__doc__)

    parser.add_argument(
        "science_path",
        type=Path,
        help="Path to directories containing the beam-wise science measurementsets that will have solutions copied over and applied.",
    )
    parser.add_argument(
        "calibrated_bandpass_path",
        type=Path,
        default=None,
        help="Path to directory containing the uncalibrated beam-wise measurement sets that contain the bandpass calibration source. If None then the '--sky-model-directory' should be provided. ",
    )
    parser.add_argument(
        "--split-path",
        type=Path,
        default=Path("."),
        help="Location to write field-split MSs to. Will attempt to use the parent name of a directory when writing out a new MS. ",
    )
    parser.add_argument(
        "--holofile",
        type=Path,
        default=None,
        help="Path to the holography FITS cube used for primary beam corrections",
    )

    parser.add_argument(
        "--expected-ms",
        type=int,
        default=36,
        help="The expected number of measurement sets to find. ",
    )
    parser.add_argument(
        "--calibrate-container",
        type=Path,
        default="aocalibrate.sif",
        help="Path to container that holds AO calibrate and applysolutions. ",
    )
    parser.add_argument(
        "--flagger-container",
        type=Path,
        default="flagger.sif",
        help="Path to container with aoflagger software. ",
    )
    parser.add_argument(
        "--wsclean-container",
        type=Path,
        default=None,
        help="Path to the wsclean singularity container",
    )
    parser.add_argument(
        "--yandasoft-container",
        type=Path,
        default=None,
        help="Path to the singularity container with yandasoft",
    )
    parser.add_argument(
        "--cluster-config",
        type=str,
        default="petrichor",
        help="Path to a cluster configuration file, or a known cluster name. ",
    )
    parser.add_argument(
        "--selfcal-rounds",
        type=int,
        default=2,
        help="The number of selfcalibration rounds to perfrom. ",
    )
    parser.add_argument(
        "--zip-ms",
        action="store_true",
        help="Zip up measurement sets as imaging and self-calibration is carried out.",
    )
    parser.add_argument(
        "--run-aegean",
        action="store_true",
        help="Run the aegean source finder on images. ",
    )
    parser.add_argument(
        "--aegean-container",
        type=Path,
        default=None,
        help="Path to the singularity container with aegean",
    )
    parser.add_argument(
        "--no-imaging",
        action="store_true",
        help="Do not perform any imaging, only derive bandpass solutions and apply to sources. ",
    )
    parser.add_argument(
        "--reference-catalogue-directory",
        type=Path,
        default=None,
        help="Path to the directory containing the ICFS, NVSS and SUMSS referenece catalogues. These are required for validaiton plots. ",
    )

    return parser


def cli() -> None:
    import logging

    # logger = logging.getLogger("flint")
    logger.setLevel(logging.INFO)

    parser = get_parser()

    args = parser.parse_args()

    setup_run_process_science_field(
        cluster_config=args.cluster_config,
        science_path=args.science_path,
        bandpass_path=args.calibrated_bandpass_path,
        split_path=args.split_path,
        flagger_container=args.flagger_container,
        calibrate_container=args.calibrate_container,
        holofile=args.holofile,
        expected_ms=args.expected_ms,
        wsclean_container=args.wsclean_container,
        yandasoft_container=args.yandasoft_container,
        rounds=args.selfcal_rounds,
        zip_ms=args.zip_ms,
        run_aegean=args.run_aegean,
        aegean_container=args.aegean_container,
        no_imaging=args.no_imaging,
        reference_catalogue_directory=args.reference_catalogue_directory,
    )


if __name__ == "__main__":
    cli()
