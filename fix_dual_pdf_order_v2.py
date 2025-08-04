#!/usr/bin/env python3
"""
Fix for dual PDF page order issue in babeldoc - Version 2
This version swaps the PDFs themselves instead of the rectangles
"""

import pymupdf


def patched_create_side_by_side_dual_pdf(
    self,
    original_pdf: pymupdf.Document,
    translated_pdf: pymupdf.Document,
    dual_out_path: str,
    translation_config,
) -> pymupdf.Document:
    """Create a dual PDF with side-by-side pages (original and translation).
    
    FIXED VERSION: This correctly implements the dual_translate_first logic.
    When dual_translate_first = False: original on left, translated on right
    When dual_translate_first = True: translated on left, original on right
    """
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"DUAL PDF FIX V2: Creating dual PDF with dual_translate_first = {translation_config.dual_translate_first}")
    
    # Create a new PDF for side-by-side pages
    dual = pymupdf.open()
    page_count = min(original_pdf.page_count, translated_pdf.page_count)

    for page_id in range(page_count):
        # Get pages from both PDFs
        orig_page = original_pdf[page_id]
        trans_page = translated_pdf[page_id]
        rotate_angle = orig_page.rotation
        total_width = orig_page.rect.width + trans_page.rect.width
        max_height = max(orig_page.rect.height, trans_page.rect.height)
        left_width = (
            trans_page.rect.width
            if trans_page.rect.width < orig_page.rect.width
            else orig_page.rect.width
        )
        # Reset rotation for both pages
        orig_page.set_rotation(0)
        trans_page.set_rotation(0)

        # Create new page with combined width
        dual_page = dual.new_page(width=total_width, height=max_height)

        # Define rectangles for left and right sides
        rect_left = pymupdf.Rect(0, 0, left_width, max_height)
        rect_right = pymupdf.Rect(left_width, 0, total_width, max_height)

        # FIXED LOGIC: Directly control which PDF goes where
        if translation_config.dual_translate_first:
            # Translated on left, original on right
            logger.debug(f"Page {page_id}: Placing TRANSLATED on LEFT, ORIGINAL on RIGHT")
            try:
                dual_page.show_pdf_page(
                    rect_left,
                    translated_pdf,
                    page_id,
                    keep_proportion=True,
                    rotate=-rotate_angle,
                )
            except Exception as e:
                logger.warning(f"Failed to show translated page on left: {e}")
            try:
                dual_page.show_pdf_page(
                    rect_right,
                    original_pdf,
                    page_id,
                    keep_proportion=True,
                    rotate=-rotate_angle,
                )
            except Exception as e:
                logger.warning(f"Failed to show original page on right: {e}")
        else:
            # Original on left, translated on right (this is what we want)
            logger.debug(f"Page {page_id}: Placing ORIGINAL on LEFT, TRANSLATED on RIGHT")
            try:
                dual_page.show_pdf_page(
                    rect_left,
                    original_pdf,
                    page_id,
                    keep_proportion=True,
                    rotate=-rotate_angle,
                )
            except Exception as e:
                logger.warning(f"Failed to show original page on left: {e}")
            try:
                dual_page.show_pdf_page(
                    rect_right,
                    translated_pdf,
                    page_id,
                    keep_proportion=True,
                    rotate=-rotate_angle,
                )
            except Exception as e:
                logger.warning(f"Failed to show translated page on right: {e}")

    return dual


def apply_dual_pdf_fix_v2():
    """Apply the monkey patch to fix dual PDF page order - Version 2"""
    try:
        from babeldoc.format.pdf.document_il.backend.pdf_creater import (
            PDFCreater,
        )
        
        # Apply the patch
        PDFCreater.create_side_by_side_dual_pdf = patched_create_side_by_side_dual_pdf
        
        print("Successfully patched dual PDF creation logic (V2)")
        return True
    except Exception as e:
        print(f"Failed to apply dual PDF patch (V2): {e}")
        return False


if __name__ == "__main__":
    apply_dual_pdf_fix_v2()