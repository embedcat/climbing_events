from openpyxl import Workbook, load_workbook
from openpyxl.writer.excel import save_virtual_workbook

from events import services
from events.models import Event


def load_template(filename: str) -> Workbook or None:
    try:
        return load_workbook(filename=filename)
    except FileNotFoundError:
        return None


def export_participants_to_start_list(event: Event):
    ROW_OFFSET = 8
    book = load_workbook(filename='static/events/xl_templates/startlist_template.xlsx')
    sheet = book.active
    sheet.cell(row=1, column=1).value = 'Скалодром "МАССИВ"'
    sheet.cell(row=2, column=1).value = event.title
    sheet.merge_cells(start_row=3, start_column=6, end_row=3, end_column=8)
    sheet.cell(row=3, column=6).value = event.date

    for set_no in range(event.set_num):
        sheet = book.copy_worksheet(book.worksheets[0])
        sheet.title = f'Сет {set_no + 1}'
        sheet.cell(row=5, column=1).value = sheet.title
        for index, p in enumerate(event.participant.filter(set_index=set_no).order_by('last_name')):
            sheet.cell(row=ROW_OFFSET + index, column=1).value = index + 1
            sheet.cell(row=ROW_OFFSET + index, column=2).value = f'{p.last_name} {p.first_name}'
            sheet.cell(row=ROW_OFFSET + index, column=3).value = p.birth_year
            sheet.cell(row=ROW_OFFSET + index, column=4).value = p.get_gender_display()
            sheet.cell(row=ROW_OFFSET + index, column=5).value = p.city
            sheet.cell(row=ROW_OFFSET + index, column=6).value = p.get_grade_display()
            sheet.cell(row=ROW_OFFSET + index, column=7).value = p.team
            group_list = services.get_group_list(event=event)
            sheet.cell(row=ROW_OFFSET + index, column=8).value = group_list[p.group_index] if group_list != [] else ''
            sheet.cell(row=ROW_OFFSET + index, column=9).value = p.pin
    # book.save(filename='startlist.xlsx')
    book.remove(book.worksheets[0])
    book.close()

    return save_virtual_workbook(book)


def export_result(event: Event):
    ROW_OFFSET = 9
    HEADS_ROW = 8
    book = load_workbook(filename='static/events/xl_templates/result_template.xlsx')
    sheet = book.active
    sheet.cell(row=1, column=1).value = 'Скалодром "МАССИВ"'
    sheet.cell(row=2, column=1).value = event.title
    sheet.merge_cells(start_row=3, start_column=6, end_row=3, end_column=8)
    sheet.cell(row=3, column=6).value = event.date

    result = services.get_results(event=event)
    # routes = event.route.all().order_by('number')

    for results, scores, gender in ([result['female'], result['routes_score_male'], 'Ж'],):
        for group in results:
            title = f"{group['name']}_{gender}"
            sheet = book.copy_worksheet(book.worksheets[0])
            sheet.title = title
            for index, p in enumerate(group['data']):
                sheet.cell(row=ROW_OFFSET + index, column=1).value = index + 1
                sheet.cell(row=ROW_OFFSET + index,
                           column=2).value = f"{p['participant'].last_name} {p['participant'].first_name}"
                sheet.cell(row=ROW_OFFSET + index, column=3).value = p['participant'].birth_year
                sheet.cell(row=ROW_OFFSET + index, column=4).value = p['participant'].city
                sheet.cell(row=ROW_OFFSET + index, column=5).value = p['participant'].get_grade_display()
                sheet.cell(row=ROW_OFFSET + index, column=6).value = p['participant'].team
                sheet.cell(row=ROW_OFFSET + index, column=7).value = p['score']
                for num, accent in enumerate(p['accents']):
                    sheet.cell(row=HEADS_ROW, column=8 + num).value = f"T#{num + 1}"
                    # sheet.cell(row=HEADS_ROW - 1, column=8 + num).value = routes[num].grade
                    # sheet.cell(row=HEADS_ROW - 2, column=8 + num).value = scores[num]
                    sheet.cell(row=ROW_OFFSET + index, column=8 + num).value = accent.accent
                sheet.cell(row=HEADS_ROW, column=8 + len(p['accents'])).value = "Итог"
                sheet.cell(row=ROW_OFFSET + index, column=8 + len(p['accents'])).value = p['score']

    book.remove(book.worksheets[0])
    return save_virtual_workbook(book)
